import random
import uuid
from typing import List, Set
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import FAISS


class QuestionService:
    def __init__(self, llm: ChatOpenAI = None):
        # Use higher temperature for randomness
        self.llm = llm or ChatOpenAI(model="gpt-4o", temperature=0.7)
        
        # Multiple prompt variations for diversity
        self.question_prompts = [
            """You are an expert educator creating study questions. Generate {n} unique, thought-provoking questions based on the provided content.
Focus on {focus_area}. Mix difficulty levels from basic recall to analytical thinking.
Create questions that encourage deep understanding rather than memorization.

Content:
---
{context}
---

Generate exactly {n} distinct questions as a numbered list:""",

            """As a skilled tutor, create {n} diverse study questions from the given material.
Emphasize {focus_area} and ensure questions test different cognitive levels:
- Some should test comprehension and recall
- Others should require analysis and application
- Include questions that connect concepts

Material:
---
{context}
---

Provide {n} unique questions in numbered format:""",

            """You are designing an assessment. Create {n} varied questions based on the content below.
Prioritize {focus_area} and ensure each question:
- Tests different aspects of the material
- Uses varied question formats (what, how, why, compare, analyze)
- Ranges from introductory to advanced difficulty

Source content:
---
{context}
---

Generate {n} distinct study questions:""",

            """Create {n} educational questions that help students master this content.
Focus particularly on {focus_area}. Design questions that:
- Encourage critical thinking beyond simple facts
- Cover different topics within the material
- Progress from easier concepts to more complex ones

Study material:
---
{context}
---

List {n} unique questions with numbers:"""
        ]
        
        # Diverse query variations to get different content sections
        self.query_variations = [
            "key concepts and main ideas",
            "important principles and theories", 
            "fundamental knowledge and core topics",
            "essential information and critical points",
            "primary themes and significant details",
            "crucial elements and central concepts",
            "main topics and important facts",
            "core material and key learning points",
            "significant concepts and vital information",
            "important theories and practical applications",
            "foundational knowledge and advanced concepts",
            "basic principles and complex ideas"
        ]
        
        # Focus areas for question generation
        self.focus_areas = [
            "conceptual understanding",
            "practical applications", 
            "theoretical foundations",
            "real-world connections",
            "analytical thinking",
            "problem-solving skills",
            "critical analysis",
            "comparative understanding",
            "synthesis and evaluation",
            "cause and effect relationships"
        ]
    
    def generate_questions(self, vectorstore: FAISS, n: int = 5, k: int = 8) -> List[str]:
        """Generate diverse study questions with randomness to avoid repetition."""
        n = max(1, min(10, int(n)))
        
        # Add randomness to retrieval parameters
        random_k = random.randint(max(6, k-2), min(12, k+4))
        random_fetch_k = random.randint(16, 24)
        
        # Use random query to get different document chunks
        random_query = random.choice(self.query_variations)
        
        # Randomly choose search type for variety
        search_type = random.choice(["similarity", "mmr", "similarity_score_threshold"])
        search_kwargs = {"k": random_k, "fetch_k": random_fetch_k}
        
        # For similarity_score_threshold, add score threshold
        if search_type == "similarity_score_threshold":
            search_kwargs["score_threshold"] = random.uniform(0.3, 0.7)
            
        retriever = vectorstore.as_retriever(
            search_type=search_type,
            search_kwargs=search_kwargs
        )
        
        # Get documents with random query
        docs = retriever.get_relevant_documents(random_query)
        
        # Randomly shuffle and sample documents for variety
        if len(docs) > random_k:
            docs = random.sample(docs, random_k)
        else:
            random.shuffle(docs)
            
        # Create context with random ordering
        context = "\n\n".join(d.page_content for d in docs)
        
        # Randomly select prompt template and focus area
        prompt_template = random.choice(self.question_prompts)
        focus_area = random.choice(self.focus_areas)
        
        # Create dynamic prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_template)
        ])
        
        # Generate questions with randomness
        chain = (prompt | self.llm | StrOutputParser())
        
        # Add session ID for additional randomness
        session_id = str(uuid.uuid4())[:8]
        
        try:
            raw = chain.invoke({
                "n": n, 
                "context": context, 
                "focus_area": focus_area,
                "session": session_id
            })
            
            # Parse questions more robustly
            questions = self._parse_questions(raw, n)
            
            # Ensure uniqueness and variety
            questions = self._ensure_question_diversity(questions, n)
            
            return questions[:n]
            
        except Exception as e:
            # Fallback with basic prompt if advanced generation fails
            return self._fallback_generation(vectorstore, n, k)
    
    def _parse_questions(self, raw_output: str, expected_count: int) -> List[str]:
        """Parse and clean questions from LLM output."""
        lines = raw_output.split('\n')
        questions = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Remove numbering (1., 2), bullet points, etc.
            cleaned = line
            for prefix in ['1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '10.', 
                          '•', '-', '*', '1)', '2)', '3)', '4)', '5)', '6)', '7)', '8)', '9)', '10)']:
                if cleaned.startswith(prefix):
                    cleaned = cleaned[len(prefix):].strip()
                    break
            
            # Only include actual questions
            if cleaned and (cleaned.endswith('?') or len(cleaned) > 10):
                questions.append(cleaned)
        
        return questions
    
    def _ensure_question_diversity(self, questions: List[str], target_count: int) -> List[str]:
        """Ensure questions are diverse and not repetitive."""
        if not questions:
            return []
            
        # Remove duplicates while preserving order
        seen = set()
        unique_questions = []
        
        for q in questions:
            q_lower = q.lower().strip()
            # Check for substantial similarity (not just exact duplicates)
            is_similar = any(
                self._are_questions_similar(q_lower, existing.lower()) 
                for existing in seen
            )
            
            if not is_similar:
                seen.add(q_lower)
                unique_questions.append(q)
        
        return unique_questions
    
    def _are_questions_similar(self, q1: str, q2: str, threshold: float = 0.7) -> bool:
        """Check if two questions are too similar."""
        # Simple similarity check based on word overlap
        words1 = set(q1.split())
        words2 = set(q2.split())
        
        if not words1 or not words2:
            return False
            
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        jaccard_similarity = intersection / union if union > 0 else 0
        return jaccard_similarity > threshold
    
    def _fallback_generation(self, vectorstore: FAISS, n: int, k: int) -> List[str]:
        """Fallback question generation if advanced method fails."""
        try:
            retriever = vectorstore.as_retriever(search_kwargs={"k": k})
            docs = retriever.get_relevant_documents("study questions from content")
            context = "\n\n".join(d.page_content for d in docs)
            
            basic_prompt = ChatPromptTemplate.from_messages([
                ("system", f"Create {n} different study questions from this content:\n\n{{context}}\n\nQuestions:")
            ])
            
            chain = (basic_prompt | self.llm | StrOutputParser())
            raw = chain.invoke({"context": context})
            
            questions = [q.strip() for q in raw.split('\n') if q.strip() and '?' in q]
            return questions[:n] if questions else [f"What are the key concepts in this material? (Question {i+1})" for i in range(n)]
            
        except Exception:
            # Ultimate fallback
            return [f"What are the main ideas discussed in this content? (Generated question {i+1})" for i in range(n)]