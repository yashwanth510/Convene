"""Isolated browser fixture: no real API calls and no production database access."""

import tempfile
import httpx
from backend.config import config
from backend.main import create_app
from backend.llm.gateway import Gateway
from tests.conftest import fake_transport

config.APP_ENV = "development"
config.INVITE_CODE = ""
for field in (
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
    "MISTRAL_API_KEY",
    "TAVILY_API_KEY",
):
    setattr(config, field, "synthetic-test-key")
folder = tempfile.TemporaryDirectory(prefix="convene-browser-")
app = create_app(
    "sqlite+aiosqlite:///" + folder.name + "/test.db",
    gateway_factory=lambda: Gateway(
        httpx.AsyncClient(transport=httpx.MockTransport(fake_transport))
    ),
)
