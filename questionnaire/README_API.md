# PDF Tutor API Documentation

## Overview
The PDF Tutor API provides a backend service for PDF-based learning and evaluation. It allows you to upload PDFs, generate study questions, and evaluate answers using AI.

## Architecture
- **Backend**: FastAPI with Python
- **Frontend**: Streamlit (separate client)
- **AI**: OpenAI GPT-4o + Embeddings
- **Vector Store**: FAISS
- **PDF Processing**: PyPDF/PyMuPDF

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables
```bash
export OPENAI_API_KEY="your-openai-api-key"
```

### 3. Start the API Server
```bash
# Development mode
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 4. Start the Streamlit Frontend
```bash
streamlit run streamlit_app.py
```

## API Endpoints

### Health Check
- **GET** `/` - Basic health check
- **GET** `/health` - Detailed health status

### PDF Management
- **POST** `/upload-pdf` - Upload a PDF file
- **POST** `/index-pdf/{filename}` - Index PDF into vector store
- **GET** `/collections` - List available collections

### Learning Features
- **POST** `/generate-questions` - Generate study questions
- **POST** `/evaluate-answers` - Evaluate student answers

## API Usage Examples

### Upload and Index PDF
```python
import requests

# Upload PDF
with open('textbook.pdf', 'rb') as f:
    files = {'file': ('textbook.pdf', f, 'application/pdf')}
    response = requests.post('http://localhost:8000/upload-pdf', files=files)
    print(response.json())

# Index PDF
data = {'collection_name': 'textbook'}
response = requests.post('http://localhost:8000/index-pdf/textbook.pdf', json=data)
print(response.json())
```

### Generate Questions
```python
data = {
    'collection_name': 'textbook',
    'num_questions': 5
}
response = requests.post('http://localhost:8000/generate-questions', json=data)
questions = response.json()['questions']
```

### Evaluate Answers
```python
data = {
    'collection_name': 'textbook',
    'answers': [
        {'question': 'What is machine learning?', 'answer': 'ML is...'},
        {'question': 'Explain neural networks', 'answer': 'Neural networks are...'}
    ]
}
response = requests.post('http://localhost:8000/evaluate-answers', json=data)
results = response.json()
```

## Response Models

### Upload Response
```json
{
    "message": "File textbook.pdf uploaded successfully",
    "filename": "textbook.pdf", 
    "suggested_collection_name": "textbook"
}
```

### Questions Response
```json
{
    "questions": [
        "What are the main principles of machine learning?",
        "How do neural networks process information?",
        "What is the difference between supervised and unsupervised learning?"
    ],
    "collection_name": "textbook"
}
```

### Evaluation Results
```json
[
    {
        "question": "What is machine learning?",
        "answer": "ML is a subset of AI...",
        "ideal_answer": "Machine learning is a method of data analysis...",
        "score": 8,
        "reasoning": "Good understanding of core concepts..."
    }
]
```

## Mobile/Web Integration

The FastAPI backend can be consumed by any client:

### Android (Kotlin/Java)
```kotlin
// Using Retrofit
interface TutorAPI {
    @POST("generate-questions")
    suspend fun generateQuestions(@Body request: QuestionRequest): QuestionsResponse
    
    @POST("evaluate-answers") 
    suspend fun evaluateAnswers(@Body request: EvaluationRequest): List<EvaluationResult>
}
```

### React/Next.js
```javascript
const generateQuestions = async (collectionName, numQuestions) => {
    const response = await fetch('http://localhost:8000/generate-questions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            collection_name: collectionName,
            num_questions: numQuestions
        })
    });
    return response.json();
};
```

### Flutter (Dart)
```dart
class TutorAPI {
    static const baseUrl = 'http://localhost:8000';
    
    static Future<List<String>> generateQuestions(String collection, int count) async {
        final response = await http.post(
            Uri.parse('$baseUrl/generate-questions'),
            headers: {'Content-Type': 'application/json'},
            body: json.encode({
                'collection_name': collection,
                'num_questions': count
            })
        );
        final data = json.decode(response.body);
        return List<String>.from(data['questions']);
    }
}
```

## Error Handling

All endpoints return proper HTTP status codes:
- `200` - Success
- `400` - Bad Request (invalid input)
- `404` - Not Found (collection/file not found)
- `503` - Service Unavailable (API key missing, services not initialized)
- `500` - Internal Server Error

## Configuration

### Environment Variables
- `OPENAI_API_KEY` - Required for AI features
- `API_BASE_URL` - Frontend API endpoint (default: http://localhost:8000)

### File Storage
- PDFs: `uploads/` directory
- Vector stores: `vectorstores/` directory

## Production Deployment

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### API Documentation
Once running, visit:
- Interactive docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI spec: http://localhost:8000/openapi.json