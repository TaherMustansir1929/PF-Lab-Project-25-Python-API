# ============================================================================
# FILE: schemas.py
# ============================================================================

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List

class QuizSessionCreate(BaseModel):
    session_id: str
    student_id: str = Field(..., max_length=50)
    course: str = Field(..., max_length=200)
    topic: str = Field(..., max_length=200)
    difficulty: int
    current_mcq: str = ""
    options: dict = {}
    user_answer: str = "A"
    correct_answer: str = "A"
    explanation: str = ""
    score: int = 0
    total_questions: int = 0
    feedback: str = ""
    phase: str = "generate_mcq"
    created_at: str

class QuizSessionUpdate(BaseModel):
    difficulty: Optional[int] = None
    current_mcq: Optional[str] = None
    options: Optional[dict] = None
    user_answer: Optional[str] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    score: Optional[int] = None
    total_questions: Optional[int] = None
    feedback: Optional[str] = None
    phase: Optional[str] = None

class QuizCreate(BaseModel):
    session_id: str
    student_id: str = Field(..., max_length=50)
    course: str = Field(..., max_length=200)
    topic: str = Field(..., max_length=200)
    final_difficulty: int
    score: int
    total_questions: int
    
class QuizUpdate(BaseModel):
    final_difficulty: Optional[int] = None
    score: Optional[int] = None
    total_questions: Optional[int] = None
