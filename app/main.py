"""
Nexus — Main FastAPI Application.

Entry point for the autonomous AI task worker.
Serves the web UI and handles WebSocket communication
for real-time agent status updates and human-in-the-loop approval.
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.agent.core import AgentCore
from app.config import settings, ensure_directories

# ── Logging Setup ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Global State ──
agent: AgentCore | None = None
active_websocket: WebSocket | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App startup and shutdown lifecycle."""
    global agent
    ensure_directories()
    agent = AgentCore()
    logger.info("🚀 Nexus AI Task Worker started")
    logger.info(f"   LLM: {settings.LLM_MODEL} via {settings.LLM_BASE_URL}")
    logger.info(f"   Mock Portal: {settings.MOCK_PORTAL_URL}")
    yield
    # Shutdown
    if agent:
        await agent.cleanup()
    logger.info("Nexus shutdown complete")


app = FastAPI(
    title="Nexus — Autonomous AI Task Worker",
    description="An AI worker that autonomously completes IT support tasks",
    lifespan=lifespan,
)

# ── Static Files & Templates ──
static_dir = os.path.join(os.path.dirname(__file__), "ui", "static")
templates_dir = os.path.join(os.path.dirname(__file__), "ui", "templates")

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

# Mount screenshots directory for serving captured images
screenshots_dir = os.path.abspath(settings.SCREENSHOTS_DIR)
os.makedirs(screenshots_dir, exist_ok=True)
app.mount("/screenshots", StaticFiles(directory=screenshots_dir), name="screenshots")


# ── Routes ──

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main chat UI."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "agent_ready": agent is not None,
        "model": settings.LLM_MODEL,
    }


# ── WebSocket ──

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time agent communication."""
    global active_websocket
    
    await websocket.accept()
    active_websocket = websocket
    logger.info("WebSocket client connected")
    
    try:
        while True:
            # Receive message from client
            raw = await websocket.receive_text()
            data = json.loads(raw)
            
            if data.get("type") == "task":
                # User submitted a new task
                user_input = data.get("input", "")
                if user_input and agent:
                    # Run agent in background task
                    asyncio.create_task(run_agent_task(websocket, user_input))
                    
            elif data.get("type") == "approval":
                # User submitted an approval decision
                step_id = data.get("step_id")
                approved = data.get("approved", False)
                reason = data.get("reason", "")
                if agent and step_id is not None:
                    agent.submit_approval(step_id, approved, reason)
                    
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
        active_websocket = None
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        active_websocket = None


async def run_agent_task(websocket: WebSocket, user_input: str):
    """Run an agent task and stream updates via WebSocket."""
    
    async def status_callback(data: dict):
        """Send status updates to the WebSocket client."""
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.error(f"Failed to send status update: {e}")
    
    async def approval_callback(data: dict):
        """Send approval requests to the WebSocket client."""
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.error(f"Failed to send approval request: {e}")
    
    # Wire up callbacks
    agent.set_status_callback(status_callback)
    agent.set_approval_callback(approval_callback)
    
    # Run the agent
    try:
        result = await agent.run(user_input)
        logger.info(f"Task completed: {result.get('status', 'unknown')}")
    except Exception as e:
        logger.error(f"Agent task failed: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "task_error",
                "error": str(e),
                "summary": f"Task failed: {str(e)}",
            })
        except Exception:
            pass


# ── Entry Point ──

def main():
    """Run the application."""
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.MAIN_APP_PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
