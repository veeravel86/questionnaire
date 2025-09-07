from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import FAISS


class QuestionService:
    def __init__(self, llm: ChatOpenAI = None):
        self.llm = llm or ChatOpenAI(model="gpt-4o", temperature=0)
        self.question_gen_prompt = ChatPromptTemplate.from_messages([
            ("system", """
You are a helpful tutor. Generate {n} diverse, open-ended study questions based only on the provided book context.
Vary difficulty from easy to hard. Output as a numbered list.
Context:
---
{context}
---
"""),
        ])
    
    def generate_questions(self, vectorstore: FAISS, n: int = 5, k: int = 8) -> list:
        """Generate study questions based on the vector store content."""
        n = max(1, min(10, int(n)))
        retriever = vectorstore.as_retriever(
            search_type="mmr", 
            search_kwargs={"k": k, "fetch_k": max(16, k*2)}
        )
        docs = retriever.get_relevant_documents("overview key concepts from the book")
        context = "\n\n".join(d.page_content for d in docs)
        
        chain = (self.question_gen_prompt | self.llm | StrOutputParser())
        raw = chain.invoke({"n": n, "context": context})
        questions = [q.strip() for q in raw.split("\n") if q.strip()]
        return questions[:n]