#!/usr/bin/env python3
"""
Example client demonstrating how to use the PDF Tutor API
This shows how Android, web apps, or other clients can integrate
"""
import requests
import json
import os
from pathlib import Path
import time

class PDFTutorClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def health_check(self):
        """Check API health"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e), "status": "unavailable"}
    
    def upload_pdf(self, file_path):
        """Upload a PDF file"""
        with open(file_path, 'rb') as f:
            files = {'file': (Path(file_path).name, f, 'application/pdf')}
            response = self.session.post(f"{self.base_url}/upload-pdf", files=files)
            response.raise_for_status()
            return response.json()
    
    def index_pdf(self, filename, collection_name):
        """Index a PDF into vector store"""
        data = {"collection_name": collection_name}
        response = self.session.post(f"{self.base_url}/index-pdf/{filename}", json=data)
        response.raise_for_status()
        return response.json()
    
    def list_collections(self):
        """Get available collections"""
        response = self.session.get(f"{self.base_url}/collections")
        response.raise_for_status()
        return response.json()["collections"]
    
    def generate_questions(self, collection_name, num_questions=3):
        """Generate study questions"""
        data = {
            "collection_name": collection_name,
            "num_questions": num_questions
        }
        response = self.session.post(f"{self.base_url}/generate-questions", json=data)
        response.raise_for_status()
        return response.json()["questions"]
    
    def evaluate_answers(self, collection_name, qa_pairs):
        """Evaluate answers"""
        data = {
            "collection_name": collection_name,
            "answers": [{"question": q, "answer": a} for q, a in qa_pairs]
        }
        response = self.session.post(f"{self.base_url}/evaluate-answers", json=data)
        response.raise_for_status()
        return response.json()

def demo_workflow():
    """Demonstrate a complete workflow"""
    print("🎓 PDF Tutor API Client Demo")
    print("=" * 40)
    
    # Initialize client
    client = PDFTutorClient()
    
    # Health check
    print("1. Checking API health...")
    health = client.health_check()
    print(f"   Status: {health.get('status', 'unknown')}")
    print(f"   OpenAI configured: {health.get('openai_configured', False)}")
    print(f"   Services ready: {health.get('services_initialized', False)}")
    print()
    
    if health.get("error"):
        print("❌ API not available. Make sure the server is running:")
        print("   python run_api.py")
        return
    
    # Check collections
    print("2. Listing available collections...")
    try:
        collections = client.list_collections()
        if collections:
            print(f"   Found {len(collections)} collections: {collections}")
            
            # Use first available collection for demo
            collection_name = collections[0]
            print(f"   Using collection: {collection_name}")
        else:
            print("   No collections found. Upload and index a PDF first.")
            print("   Example: Upload a PDF via the Streamlit app or API")
            return
    except Exception as e:
        print(f"   Error: {e}")
        return
    
    print()
    
    # Generate questions
    print("3. Generating study questions...")
    try:
        questions = client.generate_questions(collection_name, 3)
        print(f"   Generated {len(questions)} questions:")
        for i, q in enumerate(questions, 1):
            print(f"   {i}. {q}")
    except Exception as e:
        print(f"   Error generating questions: {e}")
        return
    
    print()
    
    # Simulate answering questions
    print("4. Simulating student answers...")
    sample_answers = [
        (questions[0], "This is a sample answer for the first question."),
        (questions[1], "Here's my response to the second question."),
        (questions[2], "My answer to the third question goes here.")
    ]
    
    print("5. Evaluating answers...")
    try:
        results = client.evaluate_answers(collection_name, sample_answers)
        
        total_score = 0
        count = 0
        
        for i, result in enumerate(results, 1):
            print(f"\n   Question {i}: {result['question'][:50]}...")
            print(f"   Student Answer: {result['answer'][:50]}...")
            print(f"   Ideal Answer: {result['ideal_answer'][:50]}...")
            if result['score'] is not None:
                print(f"   Score: {result['score']}/10")
                total_score += result['score']
                count += 1
            else:
                print("   Score: Not available")
            print(f"   Reasoning: {result['reasoning'][:100]}...")
        
        if count > 0:
            avg_score = total_score / count
            print(f"\n📊 Average Score: {avg_score:.1f}/10 across {count} questions")
            
            if avg_score >= 8:
                print("🏆 Excellent performance!")
            elif avg_score >= 6:
                print("👍 Good job!")
            else:
                print("📚 Keep studying!")
        
    except Exception as e:
        print(f"   Error evaluating answers: {e}")
    
    print("\n✅ Demo completed!")

def android_integration_example():
    """Show how Android app would integrate"""
    print("\n📱 Android Integration Example (Kotlin)")
    print("=" * 40)
    
    kotlin_code = '''
// Data classes (similar to Pydantic models)
data class QuestionRequest(
    val collection_name: String,
    val num_questions: Int
)

data class Answer(
    val question: String,
    val answer: String
)

data class EvaluationRequest(
    val collection_name: String,
    val answers: List<Answer>
)

// Retrofit API interface
interface PDFTutorAPI {
    @GET("health")
    suspend fun healthCheck(): HealthResponse
    
    @POST("generate-questions")
    suspend fun generateQuestions(@Body request: QuestionRequest): QuestionsResponse
    
    @POST("evaluate-answers")
    suspend fun evaluateAnswers(@Body request: EvaluationRequest): List<EvaluationResult>
    
    @GET("collections")
    suspend fun listCollections(): CollectionsResponse
}

// Usage in Android Activity/Fragment
class StudyActivity : AppCompatActivity() {
    private val api = Retrofit.Builder()
        .baseUrl("http://your-server.com:8000/")
        .addConverterFactory(GsonConverterFactory.create())
        .build()
        .create(PDFTutorAPI::class.java)
    
    private fun generateQuestions(collection: String) {
        lifecycleScope.launch {
            try {
                val request = QuestionRequest(collection, 5)
                val response = api.generateQuestions(request)
                displayQuestions(response.questions)
            } catch (e: Exception) {
                showError("Failed to generate questions: ${e.message}")
            }
        }
    }
}
'''
    print(kotlin_code)

def web_integration_example():
    """Show how web app would integrate"""  
    print("\n🌐 Web Integration Example (JavaScript)")
    print("=" * 40)
    
    js_code = '''
// JavaScript/TypeScript integration
class PDFTutorAPI {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
    }
    
    async generateQuestions(collectionName, numQuestions = 3) {
        const response = await fetch(`${this.baseUrl}/generate-questions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                collection_name: collectionName,
                num_questions: numQuestions
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        return data.questions;
    }
    
    async evaluateAnswers(collectionName, answers) {
        const response = await fetch(`${this.baseUrl}/evaluate-answers`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                collection_name: collectionName,
                answers: answers.map(qa => ({
                    question: qa.question,
                    answer: qa.answer
                }))
            })
        });
        
        return response.json();
    }
}

// React component example
function StudyComponent() {
    const [questions, setQuestions] = useState([]);
    const [answers, setAnswers] = useState({});
    const [results, setResults] = useState(null);
    const api = new PDFTutorAPI();
    
    const handleGenerateQuestions = async () => {
        try {
            const newQuestions = await api.generateQuestions('textbook', 3);
            setQuestions(newQuestions);
        } catch (error) {
            console.error('Failed to generate questions:', error);
        }
    };
    
    const handleSubmitAnswers = async () => {
        const qaList = questions.map(q => ({
            question: q,
            answer: answers[q] || ''
        }));
        
        try {
            const evalResults = await api.evaluateAnswers('textbook', qaList);
            setResults(evalResults);
        } catch (error) {
            console.error('Failed to evaluate answers:', error);
        }
    };
    
    return (
        <div>
            <button onClick={handleGenerateQuestions}>
                Generate Questions
            </button>
            {/* Question/answer form and results display */}
        </div>
    );
}
'''
    print(js_code)

if __name__ == "__main__":
    demo_workflow()
    android_integration_example()
    web_integration_example()