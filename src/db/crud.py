# ============================================================================
# FILE: crud.py
# ============================================================================

from sqlalchemy.orm import Session
from sqlalchemy import func
import src.db.models as models, src.db.schemas as schemas
from typing import Optional, Dict, Any

# ============================================================================
# QUIZ SESSION OPERATIONS (Active Sessions)
# ============================================================================

def create_quiz_session(db: Session, session_data: schemas.QuizSessionCreate):
    """Create a new quiz session"""
    db_session = models.QuizSession(**session_data.model_dump())
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

def get_quiz_session(db: Session, session_id: str) -> Optional[models.QuizSession]:
    """Get a quiz session by session_id"""
    return db.query(models.QuizSession).filter(models.QuizSession.session_id == session_id).first()

def get_quiz_session_by_student_and_session(db: Session, student_id: str, session_id: str) -> Optional[models.QuizSession]:
    """Get a quiz session by student_id and session_id"""
    return db.query(models.QuizSession).filter(
        models.QuizSession.student_id == student_id,
        models.QuizSession.session_id == session_id
    ).first()

def update_quiz_session(db: Session, session_id: str, session_update: schemas.QuizSessionUpdate):
    """Update an existing quiz session"""
    db_session = db.query(models.QuizSession).filter(models.QuizSession.session_id == session_id).first()
    if not db_session:
        return None
    for key, value in session_update.model_dump(exclude_unset=True).items():
        setattr(db_session, key, value)
    db.commit()
    db.refresh(db_session)
    return db_session

def delete_quiz_session(db: Session, session_id: str) -> bool:
    """Delete a quiz session"""
    db_session = db.query(models.QuizSession).filter(models.QuizSession.session_id == session_id).first()
    if not db_session:
        return False
    db.delete(db_session)
    db.commit()
    return True

def get_student_quiz_sessions(db: Session, student_id: str) -> list[models.QuizSession]:
    """Get all active quiz sessions for a student"""
    return db.query(models.QuizSession).filter(models.QuizSession.student_id == student_id).all()

def count_all_sessions(db: Session) -> int:
    """Count all active quiz sessions"""
    return db.query(models.QuizSession).count()

def count_unique_students_with_sessions(db: Session) -> int:
    """Count unique students with active sessions"""
    return db.query(func.count(func.distinct(models.QuizSession.student_id))).scalar()

def get_all_sessions_grouped_by_student(db: Session) -> Dict[str, list[str]]:
    """Get all session IDs grouped by student ID"""
    sessions = db.query(models.QuizSession.student_id, models.QuizSession.session_id).all()
    grouped = {}
    for student_id, session_id in sessions:
        if student_id not in grouped:
            grouped[student_id] = []
        grouped[student_id].append(session_id)
    return grouped

def quiz_session_to_state(session: models.QuizSession) -> Dict[str, Any]:
    """Convert a QuizSession database model to QuizState dictionary"""
    return {
        "course": session.course,
        "topic": session.topic,
        "difficulty": session.difficulty,
        "current_mcq": session.current_mcq,
        "options": session.options,
        "user_answer": session.user_answer,
        "correct_answer": session.correct_answer,
        "explanation": session.explanation,
        "score": session.score,
        "total_questions": session.total_questions,
        "feedback": session.feedback,
        "phase": session.phase,
        "created_at": session.created_at.isoformat() if hasattr(session.created_at, 'isoformat') else session.created_at,
    }

def state_to_quiz_session_update(state: Dict[str, Any]) -> schemas.QuizSessionUpdate:
    """Convert QuizState dictionary to QuizSessionUpdate schema"""
    return schemas.QuizSessionUpdate(
        difficulty=state.get("difficulty"),
        current_mcq=state.get("current_mcq"),
        options=state.get("options"),
        user_answer=state.get("user_answer"),
        correct_answer=state.get("correct_answer"),
        explanation=state.get("explanation"),
        score=state.get("score"),
        total_questions=state.get("total_questions"),
        feedback=state.get("feedback"),
        phase=state.get("phase"),
    )

# ============================================================================
# COMPLETED QUIZ OPERATIONS
# ============================================================================

def create_quiz(db: Session, quiz: schemas.QuizCreate):
    """Create a completed quiz record"""
    db_quiz = models.Quiz(**quiz.model_dump())
    db.add(db_quiz)
    db.commit()
    db.refresh(db_quiz)
    return db_quiz

def update_quiz(db: Session, session_id: str, quiz_update: schemas.QuizUpdate):
    """Update a completed quiz record"""
    db_quiz = db.query(models.Quiz).filter(models.Quiz.session_id == session_id).first()
    if not db_quiz:
        return None
    for key, value in quiz_update.model_dump(exclude_unset=True).items():
        setattr(db_quiz, key, value)
    db.commit()
    db.refresh(db_quiz)
    return db_quiz

def get_quiz(db: Session, session_id: str):
    """Get a completed quiz by session_id"""
    return db.query(models.Quiz).filter(models.Quiz.session_id == session_id).first()

def get_student_quizzes(db: Session, student_id: str, skip: int = 0, limit: int = 100):
    """Get all completed quizzes for a student"""
    return db.query(models.Quiz).filter(models.Quiz.student_id == student_id).offset(skip).limit(limit).all()