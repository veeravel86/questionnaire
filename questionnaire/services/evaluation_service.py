import re
import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import FAISS


class EvaluationService:
    def __init__(self, llm: ChatOpenAI = None):
        self.llm = llm or ChatOpenAI(model="gpt-4o", temperature=0)
        self.rag_answer_prompt = ChatPromptTemplate.from_messages([
            ("system", """
Using ONLY the provided context, write a concise, high-quality ideal answer to the question.
If the context is insufficient, say so and answer partially.
Context:
---
{context}
---
Question: {question}
Return only the answer text.
"""),
        ])
        
        self.eval_prompt = ChatPromptTemplate.from_messages([
            ("system", """
You are a strict but fair grader. Use ONLY the provided context to evaluate the student's answer.
Return ONE JSON object with exactly these keys:
- score: integer in [1,10]
- reasoning: string (1-3 sentences)
No markdown, no code fences, no extra text.
"""),
            ("user", """
Question: {question}
Student answer: {answer}
Reference context:
{context}
Return JSON now.
"""),
        ])
    
    def _extract_json(self, s: str) -> dict:
        """Extract JSON from model response."""
        s = s.strip()
        s = re.sub(r"^```(?:json)?\\s*|```$", "", s, flags=re.IGNORECASE|re.MULTILINE).strip()
        if "{" in s and "}" in s:
            s = s[s.find("{"): s.rfind("}")+1]
        try:
            return json.loads(s)
        except Exception:
            return {"score": None, "reasoning": s}
    
    def evaluate_answers(self, vectorstore: FAISS, qas: list):
        """Evaluate student answers against ideal answers from context."""
        results = []
        for q, a in qas:
            retriever = vectorstore.as_retriever(search_kwargs={"k": 6})
            docs = retriever.get_relevant_documents(q)
            context = "\n\n".join(d.page_content for d in docs)
            
            # Generate ideal answer from context
            ideal = (self.rag_answer_prompt | self.llm | StrOutputParser()).invoke({
                "question": q, 
                "context": context
            }).strip()
            
            # Grade strictly as JSON
            raw = (self.eval_prompt | self.llm | StrOutputParser()).invoke({
                "question": q,
                "answer": a or "",
                "context": context,
            })
            
            parsed = self._extract_json(raw)
            try:
                score_val = int(round(float(parsed.get("score", 0))))
            except Exception:
                score_val = None
                
            if isinstance(score_val, int):
                score_val = max(1, min(10, score_val))
                
            results.append({
                "question": q,
                "answer": a,
                "ideal_answer": ideal,
                "score": score_val,
                "reasoning": parsed.get("reasoning"),
            })
        return results