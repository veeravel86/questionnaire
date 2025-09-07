import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, status, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
import tempfile
import shutil
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from services.pdf_service import PDFService
from services.question_service import QuestionService
from services.evaluation_service import EvaluationService
from models import (
    HealthResponse, UploadResponse, IndexRequest, IndexResponse,
    CollectionsResponse, QuestionRequest, QuestionsResponse,
    EvaluationRequest, EvaluationResult, ErrorResponse
)
from security import (
    verify_api_key, limiter, security_headers_middleware, 
    check_file_size, validate_file_content, usage_tracker,
    log_security_event, api_key_manager
)

# ---------- Setup ----------
app = FastAPI(
    title="PDF Tutor API (Secured)",
    description="Secure API for PDF-based learning and evaluation system",
    version="1.0.0"
)

# Add security headers middleware
app.middleware("http")(security_headers_middleware)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware with restricted origins for production
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Restrict in production
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Only needed methods
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

# ---------- Paths ----------
APP_DIR = Path(__file__).parent
DB_DIR = APP_DIR / "vectorstores"
DB_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = APP_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# ---------- Initialize Services ----------
if not os.getenv("OPENAI_API_KEY"):
    print("Warning: OPENAI_API_KEY not set. API will fail without it.")

try:
    embeddings = OpenAIEmbeddings()
    llm = ChatOpenAI(model="gpt-4o", temperature=0.7)
    
    pdf_service = PDFService(DB_DIR, embeddings)
    question_service = QuestionService(llm)
    evaluation_service = EvaluationService(llm)
except Exception as e:
    print(f"Warning: Failed to initialize AI services: {e}")
    pdf_service = question_service = evaluation_service = None

# ---------- Public Endpoints (No Auth Required) ----------
@app.get("/")
async def root():
    return {"message": "PDF Tutor API (Secured) is running"}

@app.get("/health", response_model=HealthResponse)
@limiter.limit("10/minute")
async def health_check(request: Request):
    return HealthResponse(
        status="healthy",
        openai_configured=bool(os.getenv("OPENAI_API_KEY")),
        services_initialized=all([pdf_service, question_service, evaluation_service])
    )

# ---------- Secured Endpoints (API Key Required) ----------
@app.post("/upload-pdf", response_model=UploadResponse)
@limiter.limit("5/minute")  # Stricter limit for file uploads
async def upload_pdf(
    request: Request,
    file: UploadFile = File(...),
    api_key_info: Dict[str, Any] = Depends(verify_api_key)
):
    """Upload a PDF file (requires API key)"""
    # Log security event
    log_security_event("file_upload", {
        "api_key": api_key_info["name"],
        "filename": file.filename,
        "content_type": file.content_type,
        "ip": get_remote_address(request)
    })
    
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed"
        )
    
    # Read file content for validation
    file_content = await file.read()
    await file.seek(0)  # Reset file pointer
    
    # Check file size (50MB limit)
    check_file_size(len(file_content), 50)
    
    # Validate file content
    if not validate_file_content(file_content):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PDF file format"
        )
    
    # Save uploaded file
    file_path = UPLOAD_DIR / file.filename
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Track usage
        usage_tracker.track_request(api_key_info["name"], "upload_pdf", cost=5)
        
        return UploadResponse(
            message=f"File {file.filename} uploaded successfully",
            filename=file.filename,
            suggested_collection_name=file.filename.rsplit(".pdf", 1)[0]
        )
    except Exception as e:
        log_security_event("upload_error", {
            "api_key": api_key_info["name"],
            "error": str(e),
            "filename": file.filename
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )

@app.post("/index-pdf/{filename}", response_model=IndexResponse)
@limiter.limit("3/minute")  # AI operations are expensive
async def index_pdf(
    filename: str,
    request: IndexRequest,
    api_key_info: Dict[str, Any] = Depends(verify_api_key)
):
    """Index a PDF file into a vector store collection (requires API key)"""
    if not pdf_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PDF service not initialized"
        )
    
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {filename} not found"
        )
    
    try:
        message = pdf_service.index_pdf(file_path, request.collection_name)
        
        # Track usage (indexing is expensive)
        usage_tracker.track_request(api_key_info["name"], "index_pdf", cost=10)
        
        log_security_event("pdf_indexed", {
            "api_key": api_key_info["name"],
            "filename": filename,
            "collection": request.collection_name
        })
        
        return IndexResponse(message=message, collection_name=request.collection_name)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to index PDF: {str(e)}"
        )

@app.get("/collections", response_model=CollectionsResponse)
@limiter.limit("20/minute")
async def list_collections(
    api_key_info: Dict[str, Any] = Depends(verify_api_key)
):
    """List available vector store collections (requires API key)"""
    if not pdf_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PDF service not initialized"
        )
    
    try:
        collections = pdf_service.list_collections()
        usage_tracker.track_request(api_key_info["name"], "list_collections", cost=1)
        return CollectionsResponse(collections=collections)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list collections: {str(e)}"
        )

@app.post("/generate-questions", response_model=QuestionsResponse)
@limiter.limit("10/hour")  # AI generation is expensive
async def generate_questions(
    request: QuestionRequest,
    api_key_info: Dict[str, Any] = Depends(verify_api_key)
):
    """Generate study questions based on a collection (requires API key)"""
    if not question_service or not pdf_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Services not initialized"
        )
    
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API key not configured"
        )
    
    try:
        vectorstore = pdf_service.load_vectorstore(request.collection_name)
        questions = question_service.generate_questions(vectorstore, request.num_questions)
        
        # Track usage (AI calls are expensive)
        usage_tracker.track_request(api_key_info["name"], "generate_questions", cost=request.num_questions)
        
        log_security_event("questions_generated", {
            "api_key": api_key_info["name"],
            "collection": request.collection_name,
            "num_questions": request.num_questions
        })
        
        return QuestionsResponse(questions=questions, collection_name=request.collection_name)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection '{request.collection_name}' not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate questions: {str(e)}"
        )

@app.post("/evaluate-answers", response_model=List[EvaluationResult])
@limiter.limit("5/hour")  # Most expensive AI operation
async def evaluate_answers(
    request: EvaluationRequest,
    api_key_info: Dict[str, Any] = Depends(verify_api_key)
):
    """Evaluate student answers against ideal answers (requires API key)"""
    if not evaluation_service or not pdf_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Services not initialized"
        )
    
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API key not configured"
        )
    
    try:
        vectorstore = pdf_service.load_vectorstore(request.collection_name)
        qas = [(ans.question, ans.answer) for ans in request.answers]
        results = evaluation_service.evaluate_answers(vectorstore, qas)
        
        # Track usage (most expensive operation)
        usage_tracker.track_request(api_key_info["name"], "evaluate_answers", cost=len(request.answers) * 3)
        
        log_security_event("answers_evaluated", {
            "api_key": api_key_info["name"],
            "collection": request.collection_name,
            "num_answers": len(request.answers)
        })
        
        return [
            EvaluationResult(
                question=r["question"],
                answer=r["answer"],
                ideal_answer=r["ideal_answer"],
                score=r["score"],
                reasoning=r["reasoning"]
            )
            for r in results
        ]
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection '{request.collection_name}' not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to evaluate answers: {str(e)}"
        )

# ---------- Admin Endpoints ----------
@app.get("/admin/usage/{api_key}")
@limiter.limit("10/minute")
async def get_usage_stats(
    api_key: str,
    admin_key: Dict[str, Any] = Depends(verify_api_key)
):
    """Get usage statistics for an API key (admin only)"""
    # In production, check if admin_key has admin privileges
    usage = usage_tracker.get_usage(api_key)
    return {"api_key": api_key, "usage": usage}

@app.post("/admin/generate-api-key")
async def generate_new_api_key(
    name: str,
    admin_key: Dict[str, Any] = Depends(verify_api_key)
):
    """Generate new API key (admin only)"""
    # In production, check if admin_key has admin privileges
    new_key = api_key_manager.generate_key(name)
    return {"api_key": new_key, "name": name}

# ---------- Error Handlers ----------
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    log_security_event("server_error", {
        "error": str(exc),
        "path": str(request.url.path),
        "method": request.method
    })
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)