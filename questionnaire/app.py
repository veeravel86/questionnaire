import os
import re
import json
from pathlib import Path
import streamlit as st

# Loaders & vector store
from langchain_community.document_loaders import PyPDFLoader
try:
    from langchain_community.document_loaders import PyMuPDFLoader  # requires: pip install pymupdf
    HAS_PYMUPDF = True
except Exception:
    HAS_PYMUPDF = False

from pypdf.errors import DependencyError as PdfDependencyError
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ---------- Paths ----------
APP_DIR = Path(__file__).parent if "__file__" in globals() else Path.cwd()
DB_DIR = APP_DIR / "vectorstores"
DB_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = APP_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# ---------- API Key ----------
if not os.getenv("OPENAI_API_KEY"):
    st.warning("OPENAI_API_KEY not set. Embeddings/LLM will fail.")

embeddings = OpenAIEmbeddings()
llm = ChatOpenAI(model="gpt-4o", temperature=0)

# ---------- Indexing Logic ----------

def _load_pdf_docs(abs_path: Path):
    try:
        return PyPDFLoader(str(abs_path)).load()
    except PdfDependencyError:
        if HAS_PYMUPDF:
            st.info("PyPDF needs 'cryptography' for AES. Falling back to PyMuPDF loader…")
            return PyMuPDFLoader(str(abs_path)).load()
        else:
            st.error("This PDF appears to use AES encryption. Install 'cryptography' or 'pymupdf'.")
            raise
    except Exception as e:
        if HAS_PYMUPDF:
            st.info(f"PyPDF failed with: {e}. Trying PyMuPDF loader…")
            return PyMuPDFLoader(str(abs_path)).load()
        raise


def index_pdf(file_path: Path, collection_name: str) -> str:
    abs_path = Path(str(file_path).strip().strip("'\" ")).resolve()
    if not abs_path.exists():
        raise FileNotFoundError(f"PDF file not found at {abs_path}")

    docs = _load_pdf_docs(abs_path)
    splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=120)
    chunks = splitter.split_documents(docs)

    vs = FAISS.from_documents(chunks, embedding=embeddings)
    vs.save_local(str(DB_DIR / collection_name))

    return f"Indexed '{abs_path.name}' into collection '{collection_name}' at {DB_DIR / collection_name}"

# ---------- Question Generation ----------
QUESTION_GEN_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """
You are a helpful tutor. Generate {n} diverse, open-ended study questions based only on the provided book context.
Vary difficulty from easy to hard. Output as a numbered list.
Context:
---
{context}
---
"""),
])

# --- Helpers for parsing model JSON and building ideal answers ---
RAG_ANSWER_PROMPT = ChatPromptTemplate.from_messages([
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

EVAL_PROMPT = ChatPromptTemplate.from_messages([
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

def _extract_json(s: str) -> dict:
    s = s.strip()
    s = re.sub(r"^```(?:json)?\\s*|```$", "", s, flags=re.IGNORECASE|re.MULTILINE).strip()
    if "{" in s and "}" in s:
        s = s[s.find("{"): s.rfind("}")+1]
    try:
        return json.loads(s)
    except Exception:
        return {"score": None, "reasoning": s}

# ---------- Collection Helpers ----------
def list_collections():
    if not DB_DIR.exists():
        return []
    return [p.name for p in DB_DIR.iterdir() if p.is_dir() and ((p / "index.faiss").exists() or any(p.glob("*.faiss")))]


def load_vs(collection_name: str) -> FAISS:
    store_dir = DB_DIR / collection_name
    if not store_dir.exists():
        raise FileNotFoundError(f"No vector store for '{collection_name}'.")
    return FAISS.load_local(str(store_dir), embeddings, allow_dangerous_deserialization=True)


def generate_questions(collection_name: str, n: int = 5, k: int = 8) -> list:
    n = max(1, min(10, int(n)))
    vs = load_vs(collection_name)
    retriever = vs.as_retriever(search_type="mmr", search_kwargs={"k": k, "fetch_k": max(16, k*2)})
    docs = retriever.get_relevant_documents("overview key concepts from the book")
    context = "\n\n".join(d.page_content for d in docs)
    chain = (QUESTION_GEN_PROMPT | llm | StrOutputParser())
    raw = chain.invoke({"n": n, "context": context})
    questions = [q.strip() for q in raw.split("\n") if q.strip()]
    return questions[:n]


def evaluate_answers(collection_name: str, qas: list):
    vs = load_vs(collection_name)
    results = []
    for q, a in qas:
        retriever = vs.as_retriever(search_kwargs={"k": 6})
        docs = retriever.get_relevant_documents(q)
        context = "\n\n".join(d.page_content for d in docs)
        # Ideal answer from context
        ideal = (RAG_ANSWER_PROMPT | llm | StrOutputParser()).invoke({"question": q, "context": context}).strip()
        # Grade strictly as JSON
        raw = (EVAL_PROMPT | llm | StrOutputParser()).invoke({
            "question": q,
            "answer": a or "",
            "context": context,
        })
        parsed = _extract_json(raw)
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

# ---------- Custom Styling ----------
def apply_section_styling():
    st.markdown("""
    <style>
    .upload-section {
        background: linear-gradient(135deg, #E3F2FD 0%, #BBDEFB 100%);
        padding: 25px;
        border-radius: 15px;
        border-left: 5px solid #2196F3;
        margin: 15px 0;
        box-shadow: 0 2px 10px rgba(33, 150, 243, 0.1);
    }
    .index-section {
        background: linear-gradient(135deg, #E8F5E2 0%, #C8E6C9 100%);
        padding: 25px;
        border-radius: 15px;
        border-left: 5px solid #4CAF50;
        margin: 15px 0;
        box-shadow: 0 2px 10px rgba(76, 175, 80, 0.1);
    }
    .question-section {
        background: linear-gradient(135deg, #F3E5F5 0%, #E1BEE7 100%);
        padding: 25px;
        border-radius: 15px;
        border-left: 5px solid #9C27B0;
        margin: 15px 0;
        box-shadow: 0 2px 10px rgba(156, 39, 176, 0.1);
    }
    .results-section {
        background: linear-gradient(135deg, #FFF3E0 0%, #FFE0B2 100%);
        padding: 25px;
        border-radius: 15px;
        border-left: 5px solid #FF9800;
        margin: 15px 0;
        box-shadow: 0 2px 10px rgba(255, 152, 0, 0.1);
    }
    .section-header {
        color: #1A237E;
        font-weight: 600;
        margin-bottom: 15px;
        font-size: 1.3rem;
    }
    .stButton > button {
        background: linear-gradient(45deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.5rem 1.5rem;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
    }
    </style>
    """, unsafe_allow_html=True)

# ---------- Streamlit UI ----------
apply_section_styling()
st.title("🎓 PDF Tutor: Index, Questions & Answer Evaluation")

# Upload & index section
st.markdown('<div class="upload-section">', unsafe_allow_html=True)
st.markdown('<h3 class="section-header">📁 Upload & Index PDF</h3>', unsafe_allow_html=True)

pdf = st.file_uploader("Upload a PDF", type=["pdf"])

if pdf:
    saved_path = (UPLOAD_DIR / pdf.name).resolve()
    with open(saved_path, "wb") as f:
        f.write(pdf.getbuffer())

    st.success(f"✅ Saved: {saved_path}")
    default_collection = pdf.name.rsplit(".pdf", 1)[0]
    collection = st.text_input("Collection name", value=default_collection)

    with st.expander("🔍 Debug info"):
        st.write({
            "APP_DIR": str(APP_DIR),
            "UPLOAD_DIR": str(UPLOAD_DIR),
            "DB_DIR": str(DB_DIR),
            "saved_path_exists": saved_path.exists(),
        })

    st.markdown('<div class="index-section">', unsafe_allow_html=True)
    if st.button("🚀 Index PDF"):
        try:
            msg = index_pdf(saved_path, collection)
            st.success(f"✅ {msg}")
        except Exception as e:
            st.exception(e)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# Question generation & answering section
st.markdown("---")
st.markdown('<div class="question-section">', unsafe_allow_html=True)
st.markdown('<h3 class="section-header">🎯 Practice: Generate Questions and Submit Answers</h3>', unsafe_allow_html=True)

collections = list_collections()
if not collections:
    st.info("📚 No vector stores found yet. Index a PDF above first.")
else:
    chosen = st.selectbox("📋 Choose collection", options=collections)
    n_q = st.number_input("❓ How many questions? (max 10)", min_value=1, max_value=10, value=3, step=1)

    if st.button("✨ Generate Questions"):
        if not os.getenv("OPENAI_API_KEY"):
            st.error("🔑 OPENAI_API_KEY not set.")
        else:
            try:
                st.session_state["questions"] = generate_questions(chosen, int(n_q))
            except Exception as e:
                st.exception(e)

    if "questions" in st.session_state:
        st.markdown("### 📝 Your Questions")
        answers = []
        for idx, q in enumerate(st.session_state["questions"], start=1):
            st.write(f"**{idx}.** {q}")
            ans = st.text_area(f"💭 Your answer to Q{idx}", key=f"ans_{idx}")
            answers.append((q, ans))

        if st.button("📤 Send Answers"):
            st.markdown('<div class="results-section">', unsafe_allow_html=True)
            st.markdown('<h3 class="section-header">📊 Evaluation Results</h3>', unsafe_allow_html=True)
            
            results = evaluate_answers(chosen, answers)
            total_score = 0
            count = 0
            for r in results:
                st.write(f"**❓ Q:** {r['question']}")
                st.write(f"**✍️ Your Answer:** {r['answer']}")
                st.write(f"**💡 Ideal Answer (from context):** {r['ideal_answer']}")
                if isinstance(r.get("score"), int):
                    score = r['score']
                    if score >= 8:
                        st.success(f"🎉 Excellent! You scored {score} out of 10")
                    elif score >= 6:
                        st.warning(f"👍 Good! You scored {score} out of 10")
                    else:
                        st.error(f"📚 Needs improvement: {score} out of 10")
                else:
                    st.warning("⚠️ Score unavailable (model returned invalid JSON)")
                st.write(f"**🤔 Reasoning:** {r['reasoning']}")
                st.markdown("---")
                if isinstance(r.get("score"), int):
                    total_score += r["score"]
                    count += 1
            if count:
                avg = round(total_score / count, 2)
                if avg >= 8:
                    st.balloons()
                    st.success(f"🏆 Outstanding! Average score: {avg} / 10 across {count} question(s)")
                elif avg >= 6:
                    st.info(f"👏 Well done! Average score: {avg} / 10 across {count} question(s)")
                else:
                    st.info(f"📈 Keep practicing! Average score: {avg} / 10 across {count} question(s)")
            st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
