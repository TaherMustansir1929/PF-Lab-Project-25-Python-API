"""
Adaptive MCQ Quiz AI Agent with FastAPI Backend
Using LangGraph and Google Gemini

This provides a REST API for a quiz application with adaptive difficulty.
"""

import os
import uuid
from datetime import datetime

from agent import QuizState, generate_mcq_node, process_answer_node
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from models import (
    AnswerSubmitRequest,
    AnswerSubmitResponse,
    QuizStartRequest,
    QuizStartResponse,
    QuizStatusResponse,
)

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Adaptive MCQ Quiz API",
    description="REST API for an adaptive multiple-choice quiz system using Langchain and Google Gemini",
    version="1.0.0",
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session storage
active_sessions: dict[str, QuizState] = {}


# ============================================================================
# API ENDPOINTS
# ============================================================================


@app.post(
    "/api/quiz/mcqs",
    response_model=QuizStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_quiz(request: QuizStartRequest):
    """
    Start a new quiz session

    Creates a new quiz session with the specified course and topic,
    generates the first question, and returns the session ID.
    """
    try:
        # Check if session already exists
        if request.session_id and request.session_id in active_sessions:
            initial_state = active_sessions[request.session_id]
            session_id = request.session_id

            # Validate phase
            if initial_state["phase"] != "generate_mcq":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Already an active question in queue",
                )

            # Generate first question
            result = generate_mcq_node(initial_state)

            # Store session
            active_sessions[session_id] = result
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

            # Store session
            active_sessions[session_id] = result

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

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start quiz session: {str(e)}",
        )


@app.post("/api/quiz/answer", response_model=AnswerSubmitResponse)
async def submit_answer(request: AnswerSubmitRequest):
    """
    Submit an answer to the current question

    Processes the user's answer, provides feedback, adjusts difficulty,
    and generates the next question.
    """
    # Validate session exists
    if request.session_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz session not found or expired",
        )

    try:
        current_state = active_sessions[request.session_id]

        # Validate phase
        if current_state["phase"] != "process_answer":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active question to answer",
            )

        # Update state with user's answer
        current_state["user_answer"] = request.answer

        # Process answer (get feedback)
        feedback_result = process_answer_node(current_state)

        # Check if answer was correct
        is_correct = request.answer.upper() == feedback_result["correct_answer"].upper()
        feedback_text = feedback_result["feedback"]

        # Update state
        active_sessions[request.session_id] = feedback_result

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


@app.get("/api/quiz/status/{session_id}", response_model=QuizStatusResponse)
async def get_quiz_status(session_id: str):
    """
    Get the current status of a quiz session

    Returns session information including score, difficulty, and current phase.
    """
    if session_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz session not found or expired",
        )

    state = active_sessions[session_id]

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


@app.get("/api/quiz/end/{session_id}")
@app.delete("/api/quiz/end/{session_id}")
@app.post("/api/quiz/end/{session_id}")
async def end_quiz(session_id: str):
    """
    End a quiz session and clean up resources

    Removes the session from active sessions.
    """
    if session_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quiz session not found"
        )

    state = active_sessions[session_id]
    final_score = {
        "session_id": session_id,
        "score": state["score"],
        "total_questions": state["total_questions"],
        "accuracy": round((state["score"] / state["total_questions"] * 100), 2)
        if state["total_questions"] > 0
        else 0,
        "final_difficulty": state["difficulty"],
    }

    # Clean up session
    del active_sessions[session_id]

    return {"message": "Quiz session ended successfully", "final_results": final_score}


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "active_sessions_count": len(active_sessions),
        "active_sessions_ids": list(active_sessions.keys()),
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================================
# STARTUP EVENT
# ============================================================================


@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup"""
    # Verify Google API key is set
    if not os.getenv("GOOGLE_API_KEY"):
        print("WARNING: GOOGLE_API_KEY environment variable not set!")
    print("Adaptive MCQ Quiz API started successfully")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv

    load_dotenv()

    # Run the server
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
