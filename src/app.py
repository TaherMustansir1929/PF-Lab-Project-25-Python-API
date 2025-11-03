"""
Adaptive MCQ Quiz AI Agent with FastAPI Backend
Using LangGraph and Google Gemini

This provides a REST API for a quiz application with adaptive difficulty.
"""

import os
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

from src.agent import QuizState, generate_mcq_node, process_answer_node
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from src.models import (
    AnswerSubmitRequest,
    AnswerSubmitResponse,
    QuizStartRequest,
    QuizStartResponse,
    QuizStatusResponse,
    HealthCheckResponse,
    PFAnalyzerRequest,
    PFAnalyzerResponse,
)
from src.db.index import get_db, engine, Base
from src.db import crud, schemas

# ============================================================================
# LIFESPAN EVENT HANDLER
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the application on startup"""
    # Verify API keys are set
    if not os.getenv("GOOGLE_API_KEY") or not os.getenv("GROQ_API_KEY"):
        print("WARNING: GOOGLE_API_KEY or GROQ_API_KEY environment variable not set!")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully")
    print("Adaptive MCQ Quiz API started successfully")
    
    yield
    
    print("Adaptive MCQ Quiz API shutting down")

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Adaptive MCQ Quiz API",
    description="REST API for an adaptive multiple-choice quiz system using Langchain and Google Gemini",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# API ENDPOINTS
# ============================================================================


@app.post(
    "/api/quiz/mcqs",
    response_model=QuizStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_quiz(request: QuizStartRequest, db: Session = Depends(get_db)):
    """
    Start a new quiz session

    Creates a new quiz session with the specified course and topic,
    generates the first question, and returns the session ID.
    """
    try:
        # Check if session already exists
        if request.session_id:
            db_session = crud.get_quiz_session_by_student_and_session(
                db, request.user_id, request.session_id
            )
            
            if db_session:
                # Convert to QuizState
                initial_state = crud.quiz_session_to_state(db_session)
                session_id = request.session_id

                # Validate phase
                if initial_state["phase"] != "generate_mcq":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Already an active question in queue",
                    )

                # Generate first question
                result = generate_mcq_node(initial_state)  # type: ignore

                # Update session in database
                update_data = crud.state_to_quiz_session_update(result)  # type: ignore
                crud.update_quiz_session(db, session_id, update_data)
            else:
                # Session ID provided but not found, create new
                session_id = str(uuid.uuid4())
                
                # Initialize state
                initial_state = QuizState(
                    {
                        "course": request.course,
                        "topic": request.topic,
                        "difficulty": request.initial_difficulty,
                        "current_mcq": "",
                        "options": {},
                        "user_answer": "A",
                        "correct_answer": "A",
                        "explanation": "",
                        "score": 0,
                        "total_questions": 0,
                        "feedback": "",
                        "phase": "generate_mcq",
                        "created_at": datetime.now().isoformat(),
                    }
                )

                # Generate first question
                result = generate_mcq_node(initial_state)

                # Create session in database
                session_create = schemas.QuizSessionCreate(
                    session_id=session_id,
                    student_id=request.user_id,
                    **result
                )
                crud.create_quiz_session(db, session_create)
        else:
            # Generate unique session ID
            session_id = str(uuid.uuid4())

            # Initialize state
            initial_state = QuizState(
                {
                    "course": request.course,
                    "topic": request.topic,
                    "difficulty": request.initial_difficulty,
                    "current_mcq": "",
                    "options": {},
                    "user_answer": "A",
                    "correct_answer": "A",
                    "explanation": "",
                    "score": 0,
                    "total_questions": 0,
                    "feedback": "",
                    "phase": "generate_mcq",
                    "created_at": datetime.now().isoformat(),
                }
            )

            # Generate first question
            result = generate_mcq_node(initial_state)

            # Create session in database
            session_create = schemas.QuizSessionCreate(
                session_id=session_id,
                student_id=request.user_id,
                **result
            )
            crud.create_quiz_session(db, session_create)

        return QuizStartResponse(
            session_id=session_id,
            course=result["course"],
            topic=result["topic"],
            difficulty=result["difficulty"],
            question=result["current_mcq"],
            options=result["options"],
            question_number=result["total_questions"] + 1,
            message="Quiz session started successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start quiz session: {str(e)}",
        )


@app.post("/api/quiz/answer", response_model=AnswerSubmitResponse)
async def submit_answer(request: AnswerSubmitRequest, db: Session = Depends(get_db)):
    """
    Submit an answer to the current question

    Processes the user's answer, provides feedback, adjusts difficulty,
    and generates the next question.
    """
    # Validate session exists
    db_session = crud.get_quiz_session_by_student_and_session(
        db, request.user_id, request.session_id
    )
    
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz session not found or expired",
        )

    try:
        # Convert to QuizState
        current_state = crud.quiz_session_to_state(db_session)

        # Validate phase
        if current_state["phase"] != "process_answer":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active question to answer",
            )

        # Update state with user's answer
        current_state["user_answer"] = request.answer

        # Process answer (get feedback)
        feedback_result = process_answer_node(current_state)  # type: ignore

        # Check if answer was correct
        is_correct = request.answer.upper() == feedback_result["correct_answer"].upper()
        feedback_text = feedback_result["feedback"]

        # Update session in database
        update_data = crud.state_to_quiz_session_update(feedback_result)  # type: ignore
        crud.update_quiz_session(db, request.session_id, update_data)

        return AnswerSubmitResponse(
            session_id=request.session_id,
            is_correct=is_correct,
            feedback=feedback_text,
            score=feedback_result["score"],
            total_questions=feedback_result["total_questions"],
            new_difficulty=feedback_result["difficulty"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process answer: {str(e)}",
        )


@app.get("/api/quiz/status/{user_id}/{session_id}", response_model=QuizStatusResponse)
async def get_quiz_status(user_id: str, session_id: str, db: Session = Depends(get_db)):
    """
    Get the current status of a quiz session

    Returns session information including score, difficulty, and current phase.
    """
    db_session = crud.get_quiz_session_by_student_and_session(db, user_id, session_id)
    
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz session not found or expired",
        )

    state = crud.quiz_session_to_state(db_session)

    return QuizStatusResponse(
        session_id=session_id,
        course=state["course"],
        topic=state["topic"],
        score=state["score"],
        total_questions=state["total_questions"],
        difficulty=state["difficulty"],
        current_phase=state["phase"],
        created_at=state["created_at"],
    )


@app.get("/api/quiz/end/{user_id}/{session_id}")
@app.delete("/api/quiz/end/{user_id}/{session_id}")
@app.post("/api/quiz/end/{user_id}/{session_id}")
async def end_quiz(user_id: str, session_id: str, db: Session = Depends(get_db)):
    """
    End a quiz session and clean up resources

    Removes the session from active sessions and stores it as a completed quiz.
    """
    db_session = crud.get_quiz_session_by_student_and_session(db, user_id, session_id)
    
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Quiz session not found"
        )

    state = crud.quiz_session_to_state(db_session)
    
    final_score = {
        "session_id": session_id,
        "score": state["score"],
        "total_questions": state["total_questions"],
        "accuracy": round((state["score"] / state["total_questions"] * 100), 2)
        if state["total_questions"] > 0
        else 0,
        "final_difficulty": state["difficulty"],
    }

    # Store as completed quiz
    quiz_create = schemas.QuizCreate(
        session_id=session_id,
        student_id=user_id,
        course=state["course"],
        topic=state["topic"],
        final_difficulty=state["difficulty"],
        score=state["score"],
        total_questions=state["total_questions"],
    )
    crud.create_quiz(db, quiz_create)
    
    # Clean up active session
    crud.delete_quiz_session(db, session_id)

    return {"message": "Quiz session ended successfully", "final_results": final_score}


@app.get("/api/health")
async def health_check(db: Session = Depends(get_db)) -> HealthCheckResponse:
    """Health check endpoint"""
    active_user_count = crud.count_unique_students_with_sessions(db)
    quiz_session_count = crud.count_all_sessions(db)
    quiz_session_ids = crud.get_all_sessions_grouped_by_student(db)
    
    return HealthCheckResponse(
        status="healthy",
        active_user_count=active_user_count,
        quiz_session_count=quiz_session_count,
        quiz_session_ids=quiz_session_ids,
        timestamp=datetime.now().isoformat(),
    )

from src.agent import analyze_profile, StudentProfile

@app.post("/api/pfanalyzer", response_model=PFAnalyzerResponse)
async def pf_analyzer(request: PFAnalyzerRequest, db: Session = Depends(get_db)):
    """PF Analyzer endpoint"""
    # Get all completed quizzes for the student
    quizzes = crud.get_student_quizzes(db, request.student_id)
    
    if not quizzes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No quiz history found for student",
        )
        
    student_profile = StudentProfile(
        cgpa=request.cgpa,
        major=request.major,
        short_term_goals=request.short_term_goals,
        long_term_goals=request.long_term_goals,
        industries_of_interest=request.industries_of_interest,
        target_roles=request.target_roles,
        quiz_performance=[
            {
                "course": quiz.course,
                "topic": quiz.topic,
                "score": quiz.score,
                "total_questions": quiz.total_questions,
                "difficulty_level": quiz.final_difficulty,
                "date_attempted": quiz.created_at.isoformat() if hasattr(quiz.created_at, 'isoformat') else str(quiz.created_at),
            }
            for quiz in quizzes
        ],
    )
    
    try:
        response = analyze_profile(student_profile)

    except Exception as e:
        print(f"Error analyzing profile: {e}")
        response = "An error occurred while analyzing the profile. Try Again."

    return PFAnalyzerResponse(
        feedback=response,
        timestamp=datetime.now().isoformat(),
    )

