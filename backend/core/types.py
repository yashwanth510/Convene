from pydantic import BaseModel, Field
from typing import List, Tuple
from datetime import datetime


class Position(BaseModel):
    agent_id: str
    model_name: str
    content: str
    confidence: int = Field(ge=0, le=100)
    reasoning: str
    top_3_recommendations: List[str]
    naive_approach_rejected: str
    critical_risk: str
    sources_used: List[str]
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
