"""
Application configuration loaded from environment variables.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
import os


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # LLM Configuration
    GITHUB_TOKEN: str = Field(default="", description="GitHub PAT for Models API")
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
    GROQ_API_KEY: str = Field(default="", description="Groq API key")
    GEMINI_API_KEY: str = Field(default="", description="Gemini API key")
    LLM_MODEL: str = Field(default="gpt-4o-mini", description="LLM model name")
    LLM_BASE_URL: str = Field(
        default="https://models.inference.ai.azure.com",
        description="LLM API base URL",
    )
    LLM_TEMPERATURE: float = Field(default=0.1, description="LLM temperature")
    LLM_MAX_TOKENS: int = Field(default=4096, description="Max tokens per response")

    # Agentmail Configuration
    AGENTMAIL_API_KEY: str = Field(default="", description="Agentmail API key")
    AGENTMAIL_FROM_ADDRESS: str = Field(
        default="nexus@agentmail.to", description="Email sender address"
    )

    # Application
    MAIN_APP_PORT: int = Field(default=8000, description="Main app port")
    MOCK_PORTAL_URL: str = Field(
        default="http://localhost:5001", description="Mock IT portal URL"
    )
    MOCK_PORTAL_PORT: int = Field(default=5001, description="Mock portal port")

    # Paths
    KNOWLEDGE_DIR: str = Field(
        default="company_knowledge", description="Company knowledge directory"
    )
    SCREENSHOTS_DIR: str = Field(
        default="screenshots", description="Screenshots directory"
    )
    EXECUTION_LOGS_DIR: str = Field(
        default="execution_logs", description="Execution logs directory"
    )

    # Agent Configuration
    MAX_RETRIES: int = Field(default=3, description="Max retries per tool action")
    MAX_STEPS: int = Field(default=20, description="Max steps per task")
    APPROVAL_TIMEOUT: int = Field(
        default=300, description="Approval timeout in seconds"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Global settings instance
settings = Settings()


def ensure_directories():
    """Create required directories if they don't exist."""
    dirs = [
        settings.SCREENSHOTS_DIR,
        settings.EXECUTION_LOGS_DIR,
        settings.KNOWLEDGE_DIR,
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
