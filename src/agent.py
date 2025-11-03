from typing import Literal, TypedDict
import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq
from src.prompts import MCQ_GENERATION_PROMPT, FEEDBACK_PROMPT
from pydantic import BaseModel, Field

from dotenv import load_dotenv

load_dotenv()


class QuizState(TypedDict):
    """Represents the state of the quiz session"""

    course: str
    topic: str
    difficulty: int
    current_mcq: str
    options: dict[str, str]
    user_answer: Literal["A", "B", "C", "D"]
    correct_answer: Literal["A", "B", "C", "D"]
    explanation: str
    score: int
    total_questions: int
    feedback: str
    phase: Literal["generate_mcq", "process_answer", "provide_feedback"]
    created_at: str


class Options(BaseModel):
    A: str = Field(..., description="Option A text")
    B: str = Field(..., description="Option B text")
    C: str = Field(..., description="Option C text")
    D: str = Field(..., description="Option D text")


class MCQ(BaseModel):
    question: str = Field(..., description="Question text for the MCQ")
    options: Options = Field(..., description="The four answer options (A, B, C, D)")
    correct_answer: Literal["A", "B", "C", "D"] = Field(
        ..., description="Correct option for your question. Either of [A, B, C, D]"
    )
    explanation: str = Field(
        ...,
        description="Brief explanation of why this is correct and why others are wrong (2-3 sentences)",
    )
    difficulty: int = Field(2, le=5, ge=1, description="difficulty level out of 5")


# llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
llm = ChatGroq(model="openai/gpt-oss-120b")
# llm = ChatAnthropic(model_name="claude-sonnet-4-5", timeout=120, stop=None)


def generate_mcq_node(state: QuizState) -> QuizState:
    """Initializes a new quiz session"""

    prompt = MCQ_GENERATION_PROMPT.format(
        course=state["course"],
        topic=state["topic"],
        difficulty=state["difficulty"],
        history=state.get("current_mcq", "No previous questions."),
    )
    messages = [SystemMessage(content=prompt)]
    # chain = ChatPromptTemplate.from_messages(messages) | llm

    response_text = ""
    try:
        response = llm.invoke(messages)

        # Get the response content as string
        response_text = str(response.content).strip()
        print(f"\n\nRaw Response: {response_text}\n\n")

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            # Remove opening ```json or ``` and closing ```
            response_text = re.sub(r"^```(?:json)?\s*\n?", "", response_text)
            response_text = re.sub(r"\n?```\s*$", "", response_text)
            response_text = response_text.strip()

        # Try to extract JSON from the response
        json_match = re.search(
            r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", response_text, re.DOTALL
        )
        if json_match:
            json_str = json_match.group(0)
        else:
            json_str = response_text

        print(f"\n\nExtracted JSON: {json_str}\n\n")

        # Parse the JSON response
        parsed_data = json.loads(json_str)
        print(f"\n\nParsed Data: {parsed_data}\n\n")
        print(f"\n\nParsed Data Keys: {list(parsed_data.keys())}\n\n")

        # Create MCQ object from parsed data
        mcq_response = MCQ(**parsed_data)

        print(f"\n\nParsed MCQ: {mcq_response}\n\n")

        # Format the question with options for display
        formatted_question = f"{mcq_response.question}\n"
        # formatted_question += f"A. {mcq_response.options.A}\n"
        # formatted_question += f"B. {mcq_response.options.B}\n"
        # formatted_question += f"C. {mcq_response.options.C}\n"
        # formatted_question += f"D. {mcq_response.options.D}"

        state["current_mcq"] = formatted_question
        state["options"] = mcq_response.options.model_dump()
        state["correct_answer"] = mcq_response.correct_answer
        state["explanation"] = mcq_response.explanation
        state["difficulty"] = mcq_response.difficulty
        state["phase"] = "process_answer"

        return state
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
        print(f"Response Text: {response_text or '~No response~'}")
        raise Exception(f"Failed to parse MCQ response: {e}")
    except Exception as e:
        print(f"Error: {e}")
        raise Exception(f"Failed to generate MCQ: {e}")


def process_answer_node(state: QuizState) -> QuizState:
    # Normalize answers for comparison
    user_ans = state["user_answer"].strip().upper()
    correct_ans = state["correct_answer"].strip().upper()

    is_correct = user_ans == correct_ans

    # Update score and difficulty
    new_score = state["score"] + (1 if is_correct else 0)
    new_total = state["total_questions"] + 1

    # Adaptive difficulty adjustment
    new_difficulty = state["difficulty"]
    if is_correct and state["difficulty"] < 5:
        new_difficulty = min(5, state["difficulty"] + 1)
    elif not is_correct and state["difficulty"] > 1:
        new_difficulty = max(1, state["difficulty"] - 1)

    # Generate feedback
    feedback_prompt = FEEDBACK_PROMPT.format(
        course=state["course"],
        topic=state["topic"],
        question=state["current_mcq"],
        user_answer=user_ans,
        correct_answer=correct_ans,
        explanation=state["explanation"],
    )

    messages = [HumanMessage(content=feedback_prompt)]
    response = llm.invoke(messages)

    feedback = str(response.content).strip()

    state["score"] = new_score
    state["total_questions"] = new_total
    state["difficulty"] = new_difficulty
    state["phase"] = "generate_mcq"
    state["feedback"] = feedback

    return state

from src.prompts import create_analysis_request, PF_ANALYZER_SYSTEM_PROMPT

class StudentProfile(BaseModel):
    cgpa: float = Field(..., description="Cumulative Grade Point Average")
    major: str = Field(..., description="Student's major field of study")
    short_term_goals: str = Field(..., description="Student's short term career goals")
    long_term_goals: str = Field(..., description="Student's long term career goals")
    industries_of_interest: str = Field(..., description="Industries the student is interested in")
    target_roles: str = Field(..., description="Target job roles the student aims for")
    quiz_performance: list[dict] = Field(..., description="Performance metrics from quizzes taken by the student")

def analyze_profile(student_profile: StudentProfile) -> str:
    """Analyzes the student profile and returns a summary string."""

    analysis_request = create_analysis_request(
        {"cgpa": student_profile.cgpa,
        "major": student_profile.major,
        "short_term_goals": student_profile.short_term_goals,
        "long_term_goals": student_profile.long_term_goals,
        "industries_of_interest": student_profile.industries_of_interest,
        "target_roles": student_profile.target_roles,
        "quiz_performance": student_profile.quiz_performance
    })
    messages = [SystemMessage(content=PF_ANALYZER_SYSTEM_PROMPT), HumanMessage(content=analysis_request)]
    response = llm.invoke(messages)

    return str(response.content).strip()
