# Nexus — Autonomous AI Task Worker

> An AI worker that takes natural language tasks and autonomously completes them using a computer — understanding goals, planning actions, using tools, verifying outcomes, and involving humans only when necessary.

**Built for:** CentrAlign AI Engineering Intern Assignment  
**Author:** [Your Name]

---

## 🎯 What It Does

Nexus is an autonomous AI task worker that can:

1. **Understand** a user's natural language request and determine the end goal
2. **Plan** a sequence of actions using available tools
3. **Execute** actions using browser automation, APIs, file operations, and email
4. **Observe** results and extract useful information
5. **Adapt** when things fail — retry, try alternatives, or ask for human help
6. **Verify** whether the requested outcome was actually achieved
7. **Report** a summary with evidence (screenshots, data, logs)

### Demo Scenario: IT Support Workflow

> *"Check all our company services. If anything is down or degraded, create support tickets and notify the IT team."*

Nexus will autonomously:
- Navigate the company's IT portal to check service statuses
- Discover that VPN is **down** and CRM is **degraded**
- Follow company procedures to create P1/P2 support tickets
- Request human approval before sending external notifications
- Send email notifications to the IT team via Agentmail
- Verify that tickets were created and notifications sent
- Return a comprehensive summary with screenshots as evidence

---

## 🏗️ Architecture

```
Goal → Understand → Plan → Execute → Observe → Adapt → Verify → Complete
```

### Core Loop

```
┌─────────────────────────────────────────────────────────┐
│                    AGENT CORE LOOP                       │
│                                                         │
│  User Input ──→ [Planner] ──→ [Executor] ──→ [Observer] │
│                     ↑              │              │      │
│                     │              ↓              │      │
│                [Re-planner]   [Approval Gate]     │      │
│                     ↑              │              │      │
│                     │              ↓              ↓      │
│                [Recovery] ←── [Tool Result] ──→ [State]  │
│                                                   │      │
│                                    [Verifier] ←───┘      │
│                                        │                 │
│                                        ↓                 │
│                              [Summary + Evidence]        │
└─────────────────────────────────────────────────────────┘
```

### Components

| Component | Purpose |
|-----------|---------|
| **Planner** | Understands goals, creates executable plans, re-plans on failure |
| **Executor** | Dispatches steps to tools with parameter resolution |
| **Observer** | Analyzes tool results, extracts data, detects issues |
| **Verifier** | Confirms if the overall goal was actually achieved |
| **Recovery Manager** | Handles retries, alternatives, and escalation to humans |
| **Approval Gate** | Risk-based human-in-the-loop system (LOW/MEDIUM/HIGH) |
| **Short-Term Memory** | Current task context, plan state, observations |
| **Long-Term Memory** | Persistent company knowledge (JSON files) |
| **Execution Log** | Full audit trail of every action |

### Tools

| Tool | Risk Level | Capabilities |
|------|-----------|--------------|
| **Browser** (Playwright) | Medium | Navigate, click, type, extract text, screenshot, list elements |
| **File Operations** | Low | Read, write, list, search files |
| **API Requests** | Medium | GET, POST, PUT, DELETE with JSON |
| **Email** (Agentmail) | High | Send notifications (requires approval) |

---

## 🚀 Setup & Run

### Prerequisites

- Python 3.11+
- A GitHub Personal Access Token (for OpenAI via GitHub Models)
- An Agentmail API key (optional — falls back to mock emails)

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd Centralign

# Create virtual environment
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### Configuration

```bash
# Copy the environment template
cp .env.example .env

# Edit .env with your credentials
# Required:
GITHUB_TOKEN=your_github_personal_access_token

# Optional:
AGENTMAIL_API_KEY=your_agentmail_api_key
AGENTMAIL_FROM_ADDRESS=nexus@yourdomain.agentmail.to
```

### Running

You need two terminals:

**Terminal 1 — Mock IT Portal:**
```bash
python -m mock_portal.app
# Runs at http://localhost:5001
```

**Terminal 2 — Nexus Main App:**
```bash
python -m app.main
# Runs at http://localhost:8000
```

Then open **http://localhost:8000** in your browser.

### Running Tests

```bash
python -m pytest tests/ -v
```

---

## 🧠 Important Technical Decisions

### 1. Custom Agent Loop (not a framework wrapper)
While LangChain utilities are used for LLM API interaction, the core agent loop — planning, execution, observation, recovery, verification — is **entirely custom-built**. This demonstrates actual engineering ability rather than simply connecting APIs.

### 2. Risk-Based Approval System
Actions are classified into three risk levels:
- **LOW** (read operations): Auto-approved, no human involvement
- **MEDIUM** (internal writes): May require approval based on context
- **HIGH** (external communications): Always requires human approval

This mirrors how real enterprise systems should work — autonomy where safe, control where critical.

### 3. Dual-Interface Mock Portal
The mock IT portal exposes both **web pages** (for browser automation) and **REST APIs** (for direct API calls). This lets the agent choose the most appropriate interaction method and demonstrates flexibility.

### 4. Structured LLM Interaction
Each LLM call uses carefully crafted prompts with JSON schema enforcement. The agent doesn't have a single monolithic prompt — instead, specialized prompts for:
- Goal understanding
- Plan creation
- Result observation
- Outcome verification
- Re-planning after failures

### 5. Company Knowledge as Memory
Company procedures, escalation policies, and service information are stored as JSON files. The agent loads and uses this context to make decisions aligned with how the company actually operates (e.g., "VPN issues → notify DevOps Lead").

### 6. Real-Time WebSocket UI
The web interface receives live updates via WebSocket — the user sees the agent think, plan, execute, and verify in real-time. Approval requests appear as interactive banners.

---

## 📁 Project Structure

```
Centralign/
├── app/                          # Main application
│   ├── agent/                    # Agent core
│   │   ├── core.py               # Main orchestration loop
│   │   ├── planner.py            # Goal understanding & planning
│   │   ├── executor.py           # Tool dispatch
│   │   ├── observer.py           # Result analysis
│   │   ├── verifier.py           # Outcome verification
│   │   ├── recovery.py           # Failure handling
│   │   └── approval.py           # Human-in-the-loop
│   ├── tools/                    # Tool implementations
│   │   ├── base.py               # Abstract tool interface
│   │   ├── browser_tool.py       # Playwright browser automation
│   │   ├── file_tool.py          # File system operations
│   │   ├── api_tool.py           # HTTP API requests
│   │   └── email_tool.py         # Agentmail integration
│   ├── memory/                   # Memory systems
│   │   ├── short_term.py         # Task-scoped context
│   │   ├── long_term.py          # Persistent company knowledge
│   │   └── execution_log.py      # Audit trail
│   ├── llm/
│   │   └── client.py             # OpenAI via GitHub Models
│   ├── ui/                       # Web frontend
│   │   ├── templates/index.html
│   │   └── static/               # CSS + JS
│   ├── main.py                   # FastAPI entry point
│   └── config.py                 # Settings
├── mock_portal/                  # Simulated IT portal (Flask)
├── company_knowledge/            # Company context (JSON)
├── tests/                        # Test suite
├── requirements.txt
└── README.md
```

---

## ⚠️ Known Limitations

1. **Browser Automation Reliability**: Complex/dynamic web pages with heavy JS may cause selector issues. The mock portal is designed for reliable automation.
2. **Single Task Execution**: Processes one task at a time; no parallel task queue.
3. **LLM Dependency**: Agent quality depends heavily on the LLM's reasoning ability. GPT-4o-mini occasionally produces suboptimal plans.
4. **No Authentication Handling**: Cannot log into real websites requiring credentials.
5. **Memory Volatility**: Short-term memory is in-process only; long-term memory persists via JSON files but is not indexed for semantic retrieval.
6. **Limited Error Recovery**: Recovery is rule-based (retries + alternatives). More sophisticated recovery would use the LLM to reason about failure causes.
7. **Rate Limiting**: Multiple LLM calls per task mean potential rate limiting on free tiers.

---

## 🔮 What I Would Build Next

Given more time, I would focus on:

1. **Semantic Memory**: Replace JSON-based lookup with vector embeddings (FAISS/ChromaDB) for better context retrieval.
2. **Multi-Agent Architecture**: Specialist agents for different domains (IT, HR, Finance) coordinated by a supervisor.
3. **Learning from Feedback**: Use successful task outcomes to fine-tune prompts and improve future planning.
4. **Visual Grounding**: Screenshot analysis using vision models to understand page state, rather than relying solely on DOM extraction.
5. **Persistent Browser Sessions**: Maintain authenticated sessions across tasks.
6. **Task Scheduling**: Recurring tasks (e.g., "Check services every morning").
7. **Streaming Execution**: Let users modify the plan mid-execution.
8. **Role-Based Access Control**: Different permission levels for different AI employees.
9. **Integration Hub**: Pre-built connectors for Jira, Slack, Notion, Google Workspace.
10. **Reliability Benchmarks**: Automated evaluation suite to measure agent success rates.

---

## 🛠️ Models, APIs & Tools Used

| Component | Technology |
|-----------|-----------|
| **LLM** | OpenAI GPT-4o-mini via GitHub Models API |
| **Browser Automation** | Playwright (Chromium) |
| **Email** | Agentmail API |
| **Backend** | FastAPI + Uvicorn |
| **Mock Portal** | Flask |
| **Frontend** | Vanilla HTML/CSS/JS with WebSocket |
| **LLM Utilities** | LangChain (for OpenAI client wrappers) |
| **HTTP Client** | httpx |
| **Testing** | pytest + pytest-asyncio |

---

## 📝 Assumptions

1. The company has an internal IT portal accessible at a known URL.
2. Company procedures and contacts are documented and available.
3. The agent operates in a sandboxed environment — no access to real production systems.
4. Email notifications go through a managed service (Agentmail) rather than direct SMTP.
5. Human approval is provided via the web UI in real-time.
6. The mock portal represents a simplified but realistic version of internal IT tools.

---

## 📄 License

This project was built as a submission for the CentrAlign AI Engineering Intern assignment.
