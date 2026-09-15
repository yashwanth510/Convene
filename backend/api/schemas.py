from typing import Literal
from pydantic import BaseModel, Field
from backend.config import config


class Document(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=24000)


class RunRequest(BaseModel):
    content: str = Field(min_length=1, max_length=12000)
    request_key: str = Field(min_length=8, max_length=80)
    mode: Literal["auto", "fast", "council"] = "auto"
    panel_size: int = Field(default=config.DEBATE_PANEL_SIZE, ge=2, le=5)
    debate_rounds: int = Field(default=2, ge=1, le=3)
    chairman_model: str | None = None
    enabled_models: list[str] | None = Field(default=None, max_length=10)
    web_search_enabled: bool = True
    documents: list[Document] = Field(default_factory=list, max_length=3)


class Feedback(BaseModel):
    value: Literal[-1, 0, 1]
