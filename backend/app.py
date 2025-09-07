import warnings
warnings.filterwarnings("ignore", message="resource_tracker: There appear to be.*")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os

from config import config
from rag_system import RAGSystem

# Initialize FastAPI app
app = FastAPI(title="Course Materials RAG System", root_path="")

# Add trusted host middleware for proxy
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]
)

# Enable CORS with proper settings for proxy
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Initialize RAG system
rag_system = RAGSystem(config)

# Pydantic models for request/response
class QueryRequest(BaseModel):
    """Request model for course queries"""
    query: str
    session_id: Optional[str] = None

class SourceInfo(BaseModel):
    """Information about a source with optional lesson link"""
    title: str
    lesson_number: Optional[int] = None  
    link: Optional[str] = None
    
    class Config:
        """Ensure proper JSON serialization"""
        json_encoders = {
            # Ensure all fields are properly serialized
        }

class QueryResponse(BaseModel):
    """Response model for course queries"""
    answer: str
    sources: List[SourceInfo]
    session_id: str

class CourseStats(BaseModel):
    """Response model for course statistics"""
    total_courses: int
    course_titles: List[str]

# API Endpoints

@app.post("/api/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """Process a query and return response with sources"""
    try:
        # Create session if not provided
        session_id = request.session_id
        if not session_id:
            session_id = rag_system.session_manager.create_session()
        
        # Process query using RAG system
        answer, sources = rag_system.query(request.query, session_id)
        
        
        # Convert sources to SourceInfo objects
        source_objects = []
        for source in sources:
            if isinstance(source, dict):
                # New structured format
                source_objects.append(SourceInfo(
                    title=source.get('title', 'Unknown'),
                    lesson_number=source.get('lesson_number'),
                    link=source.get('link')
                ))
            else:
                # Fallback for string format (backward compatibility)  
                source_objects.append(SourceInfo(title=str(source)))
        
        return QueryResponse(
            answer=answer,
            sources=source_objects,
            session_id=session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/courses", response_model=CourseStats)
async def get_course_stats():
    """Get course analytics and statistics"""
    try:
        analytics = rag_system.get_course_analytics()
        return CourseStats(
            total_courses=analytics["total_courses"],
            course_titles=analytics["course_titles"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/test-sources", response_model=QueryResponse)
async def test_sources():
    """Test endpoint to verify SourceInfo serialization"""
    test_sources = [
        SourceInfo(
            title="Test Course",
            lesson_number=1,
            link="https://example.com/lesson1"
        ),
        SourceInfo(
            title="Another Course",
            lesson_number=2,
            link="https://example.com/lesson2"
        )
    ]
    
    return QueryResponse(
        answer="This is a test response",
        sources=test_sources,
        session_id="test_session"
    )

@app.on_event("startup")
async def startup_event():
    """Load initial documents on startup"""
    docs_path = "../docs"
    if os.path.exists(docs_path):
        print("Loading initial documents...")
        try:
            courses, chunks = rag_system.add_course_folder(docs_path, clear_existing=False)
            print(f"Loaded {courses} courses with {chunks} chunks")
        except Exception as e:
            print(f"Error loading documents: {e}")

# Custom static file handler with no-cache headers for development
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from pathlib import Path


class DevStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if isinstance(response, FileResponse):
            # Add no-cache headers for development
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response
    
    
# Serve static files for the frontend
app.mount("/", StaticFiles(directory="../frontend", html=True), name="static")