from pydantic import BaseModel, Field
from typing import List, Optional

# Shared Models
class Course(BaseModel):
    course_id: str
    course_name: str

# --- Learning Path Models ---

class LearningPathRequest(BaseModel):
    target_role: str = Field(..., description="The ID of the target JobRole (e.g., 'ROL-01')")
    current_skills: List[str] = Field(default=[], description="List of Skill IDs the learner already has")

class LearningPathStep(BaseModel):
    skill_id: str
    skill_name: str
    order: int
    prerequisites: List[str]
    recommended_courses: List[Course]

class LearningPathResponse(BaseModel):
    target_role: Optional[str] = None
    current_skills: Optional[List[str]] = None
    learning_path: List[LearningPathStep]
    total_skills_needed: int
    estimated_duration: Optional[str] = None
    message: Optional[str] = None

# --- Gap Analysis Models ---

class GapAnalysisRequest(BaseModel):
    target_role: str = Field(..., description="The ID of the target JobRole (e.g., 'ROL-01')")
    current_skills: List[str] = Field(default=[], description="List of Skill IDs the learner already has")

class SkillGap(BaseModel):
    skill_id: str
    skill_name: str
    priority_score: float
    unlock_score: int
    distance_from_current: int
    courses: List[Course]

class GapAnalysisResponse(BaseModel):
    target_role: Optional[str] = None
    skill_gaps: List[SkillGap]
    total_gaps: int
    message: Optional[str] = None

# --- Chat Models ---

class ChatRequest(BaseModel):
    message: str = Field(..., description="The natural language query from the user")

class ChatResponse(BaseModel):
    intent: Optional[str] = None
    reply: str
    raw_graph_data: Optional[dict] = None
