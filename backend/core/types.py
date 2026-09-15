from pydantic import BaseModel, Field
from typing import List, Tuple
from datetime import datetime


class Position(BaseModel):
    agent_id: str
    model_name: str
    content: str
    timestamp: datetime


class Review(BaseModel):
    reviewer_id: str
    reviewer_model: str
    ranked_positions: List[Tuple[str, int, str]]
    comment: str
    timestamp: datetime


class RankingResult(BaseModel):
    aggregate_ranking: List[Tuple[str, float, float]]
    convergence_score: float = Field(ge=0, le=1)
    consensus_reached: bool
