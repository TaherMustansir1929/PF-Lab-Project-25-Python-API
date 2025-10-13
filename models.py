from pydantic import BaseModel, Field
from typing import Literal, Optional

# ============================================================================
# PYDANTIC MODELS FOR API
# ============================================================================


class QuizStartRequest(BaseModel):
    """Request model to start a new quiz session"""

    course: str = Field(..., description="Course/subject name")
    topic: str = Field(..., description="Specific topic within the course")
    user_id: Optional[str] = Field(None, description="Optional user identifier")
    session_id: Optional[str] = Field(
        None, description="Optional session identifier if session exists"
    )
    initial_difficulty: int = Field(
        2, ge=1, le=5, description="Starting difficulty level (1-5)"
    )


class QuizStartResponse(BaseModel):
    """Response model for starting a quiz"""

    session_id: str
    course: str
    topic: str
    difficulty: int
    question: str
    options: dict[str, str]
    question_number: int
    message: str


class AnswerSubmitRequest(BaseModel):
    """Request model to submit an answer"""

    session_id: str = Field(..., description="Quiz session identifier")
    answer: Literal["A", "B", "C", "D"] = Field(
        ..., description="User's answer (A, B, C, or D)", pattern="^[A-Da-d]$"
    )


class AnswerSubmitResponse(BaseModel):
    """Response model after submitting an answer"""

    session_id: str
    is_correct: bool
    feedback: str
    score: int
    total_questions: int
    new_difficulty: int


class QuizStatusResponse(BaseModel):
    """Response model for quiz session status"""

    session_id: str
    course: str
    topic: str
    score: int
    total_questions: int
    difficulty: int
    current_phase: str
    created_at: str


class ErrorResponse(BaseModel):
    """Error response model"""

    error: str
    detail: Optional[str] = None
