import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
import tempfile
import shutil

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from services.pdf_service import PDFService
from services.question_service import QuestionService
from services.evaluation_service import EvaluationService
from models import (
    HealthResponse, UploadResponse, IndexRequest, IndexResponse,
    CollectionsResponse, QuestionRequest, QuestionsResponse,
    EvaluationRequest, EvaluationResult, ErrorResponse
)

# ---------- Setup ----------
app = FastAPI(
    title="PDF Tutor API",
    description="API for PDF-based learning and evaluation system",
    version="1.0.0"
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

# Models are imported from models.py

# ---------- Health Check ----------
@app.get("/")
async def root():
    return {"message": "PDF Tutor API is running"}

@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        openai_configured=bool(os.getenv("OPENAI_API_KEY")),
        services_initialized=all([pdf_service, question_service, evaluation_service])
    )

# ---------- PDF Upload & Indexing ----------
@app.post("/upload-pdf", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """Upload a PDF file"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Only PDF files are allowed"
        )
    
    # Save uploaded file
    file_path = UPLOAD_DIR / file.filename
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return UploadResponse(
            message=f"File {file.filename} uploaded successfully",
            filename=file.filename,
            suggested_collection_name=file.filename.rsplit(".pdf", 1)[0]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to upload file: {str(e)}"
        )

@app.post("/index-pdf/{filename}", response_model=IndexResponse)
async def index_pdf(filename: str, request: IndexRequest):
    """Index a PDF file into a vector store collection"""
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
        return IndexResponse(message=message, collection_name=request.collection_name)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to index PDF: {str(e)}"
        )

# ---------- Collections ----------
@app.get("/collections", response_model=CollectionsResponse)
async def list_collections():
    """List available vector store collections"""
    if not pdf_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="PDF service not initialized"
        )
    
    try:
        collections = pdf_service.list_collections()
        return CollectionsResponse(collections=collections)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to list collections: {str(e)}"
        )

# ---------- Question Generation ----------
@app.post("/generate-questions", response_model=QuestionsResponse)
async def generate_questions(request: QuestionRequest):
    """Generate study questions based on a collection"""
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

# ---------- Answer Evaluation ----------
@app.post("/evaluate-answers", response_model=List[EvaluationResult])
async def evaluate_answers(request: EvaluationRequest):
    """Evaluate student answers against ideal answers"""
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

# ---------- Error Handlers ----------
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)