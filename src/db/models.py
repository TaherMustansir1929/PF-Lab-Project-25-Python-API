# ============================================================================
# FILE: models.py
# ============================================================================

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON
from datetime import datetime
from src.db.index import Base
import uuid

# class Student(Base):
#     __tablename__ = "students"
    
#     id = Column(Integer, primary_key=True, index=True)
#     student_id = Column(String(50), unique=True, index=True, nullable=False)
#     password = Column(String(100), nullable=False)
#     created_at = Column(DateTime, default=datetime.now())
    
#     quizzes = relationship("Quiz", back_populates="student", cascade="all, delete-orphan")


class QuizSession(Base):
    """Active quiz session state"""
    __tablename__ = "quiz_sessions"
    
    session_id = Column(String(50), primary_key=True, index=True)
    student_id = Column(String(50), nullable=False, index=True)
    course = Column(String(200), nullable=False)
    topic = Column(String(200), nullable=False)
    difficulty = Column(Integer, nullable=False)
    current_mcq = Column(Text, nullable=False, default="")
    options = Column(JSON, nullable=False, default={})
    user_answer = Column(String(1), nullable=False, default="A")
    correct_answer = Column(String(1), nullable=False, default="A")
    explanation = Column(Text, nullable=False, default="")
    score = Column(Integer, nullable=False, default=0)
    total_questions = Column(Integer, nullable=False, default=0)
    feedback = Column(Text, nullable=False, default="")
    phase = Column(String(50), nullable=False, default="generate_mcq")
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Quiz(Base):
    """Completed quiz record"""
    __tablename__ = "quizzes"
    
    session_id = Column(String(50), primary_key=True, index=True)
    student_id = Column(String(50), nullable=False, index=True)
    course = Column(String(200), nullable=False)
    topic = Column(String(200), nullable=False)
    final_difficulty = Column(Integer, nullable=False)
    score = Column(Integer, nullable=False)
    total_questions = Column(Integer, nullable=False)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # student = relationship("Student", back_populates="quizzes")
