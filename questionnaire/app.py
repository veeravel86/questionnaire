import os
from pathlib import Path
import streamlit as st

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from services.pdf_service import PDFService
from services.question_service import QuestionService
from services.evaluation_service import EvaluationService

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

# Initialize services
pdf_service = PDFService(DB_DIR, embeddings)
question_service = QuestionService(llm)
evaluation_service = EvaluationService(llm)




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
            msg = pdf_service.index_pdf(saved_path, collection)
            st.success(f"✅ {msg}")
        except Exception as e:
            st.exception(e)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# Question generation & answering section
st.markdown("---")
st.markdown('<div class="question-section">', unsafe_allow_html=True)
st.markdown('<h3 class="section-header">🎯 Practice: Generate Questions and Submit Answers</h3>', unsafe_allow_html=True)

collections = pdf_service.list_collections()
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
                vs = pdf_service.load_vectorstore(chosen)
                st.session_state["questions"] = question_service.generate_questions(vs, int(n_q))
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
            
            vs = pdf_service.load_vectorstore(chosen)
            results = evaluation_service.evaluate_answers(vs, answers)
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
