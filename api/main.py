import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

from src.query_service import QueryService
from src.llm_service import LLMService
from api.models import (
    LearningPathRequest,
    LearningPathResponse,
    GapAnalysisRequest,
    GapAnalysisResponse,
    ChatRequest,
    ChatResponse
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="HeyHi Assessment API", version="1.0.0")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize global services
query_service = None
llm_service = None

@app.on_event("startup")
def startup_event():
    global query_service, llm_service
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    
    logger.info("Initializing QueryService...")
    query_service = QueryService(uri, user, password)
    
    logger.info("Initializing LLMService...")
    llm_service = LLMService(query_service)

@app.on_event("shutdown")
def shutdown_event():
    global query_service
    if query_service:
        logger.info("Closing QueryService connection...")
        query_service.close()

# --- API Endpoints ---

@app.post("/api/learning-path", response_model=LearningPathResponse)
def get_learning_path(request: LearningPathRequest):
    try:
        result = query_service.get_learning_path(
            current_skills=request.current_skills,
            target_role_id=request.target_role
        )
        return LearningPathResponse(
            target_role=request.target_role,
            current_skills=request.current_skills,
            learning_path=result.get("learning_path", []),
            total_skills_needed=result.get("total_skills_needed", 0),
            estimated_duration=result.get("estimated_duration"),
            message=result.get("message")
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Internal server error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/gap-analysis", response_model=GapAnalysisResponse)
def get_gap_analysis(request: GapAnalysisRequest):
    try:
        result = query_service.get_gap_analysis(
            current_skills=request.current_skills,
            target_role_id=request.target_role
        )
        return GapAnalysisResponse(
            target_role=request.target_role,
            skill_gaps=result.get("skill_gaps", []),
            total_gaps=result.get("total_gaps", 0),
            message=result.get("message")
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Internal server error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Chat endpoint for Part C
@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    try:
        result = llm_service.process_chat(request.message)
        return ChatResponse(
            intent=result.get("intent", "unknown"),
            reply=result.get("reply", "Something went wrong.")
        )
    except Exception as e:
        logger.error(f"Chat API internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# --- Static Files ---

frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="frontend")

@app.get("/")
def serve_index():
    index_file = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Welcome to HeyHi Assessment API"}
