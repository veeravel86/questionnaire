from pydantic import BaseModel, Field
from typing import List, Optional, Union
from enum import Enum

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"

class HealthResponse(BaseModel):
    status: HealthStatus
    openai_configured: bool
    services_initialized: bool

class UploadResponse(BaseModel):
    message: str
    filename: str
    suggested_collection_name: str

class IndexRequest(BaseModel):
    collection_name: str = Field(..., min_length=1, max_length=100, description="Name for the vector store collection")

class IndexResponse(BaseModel):
    message: str
    collection_name: str

class CollectionsResponse(BaseModel):
    collections: List[str]

class QuestionRequest(BaseModel):
    collection_name: str = Field(..., min_length=1, description="Name of the collection to generate questions from")
    num_questions: int = Field(default=3, ge=1, le=10, description="Number of questions to generate (1-10)")

class QuestionsResponse(BaseModel):
    questions: List[str]
    collection_name: str

class Answer(BaseModel):
    question: str = Field(..., min_length=1, description="The question being answered")
    answer: str = Field(default="", description="The student's answer")

class EvaluationRequest(BaseModel):
    collection_name: str = Field(..., min_length=1, description="Name of the collection to evaluate against")
    answers: List[Answer] = Field(..., min_items=1, description="List of question-answer pairs")

class EvaluationResult(BaseModel):
    question: str
    answer: str
    ideal_answer: str
    score: Optional[int] = Field(None, ge=1, le=10, description="Score from 1-10, or None if scoring failed")
    reasoning: str

class EvaluationSummary(BaseModel):
    results: List[EvaluationResult]
    total_questions: int
    average_score: Optional[float] = None
    questions_scored: int

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    status_code: int

class APIError(Exception):
    def __init__(self, message: str, status_code: int = 500, detail: str = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.message)