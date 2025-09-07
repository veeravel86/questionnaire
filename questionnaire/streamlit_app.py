import streamlit as st
from api_client import get_api_client
import os

# ---------- Configuration ----------
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
api_client = get_api_client(API_BASE_URL)

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
    .status-indicator {
        padding: 10px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .status-healthy {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .status-unhealthy {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
    }
    </style>
    """, unsafe_allow_html=True)

# ---------- Helper Functions ----------
def check_api_status():
    """Check if API is available and healthy"""
    try:
        health = api_client.health_check()
        return health, True
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}, False

def display_status_indicator(health_data, is_healthy):
    """Display API status indicator"""
    if is_healthy:
        st.markdown(f"""
        <div class="status-indicator status-healthy">
            ✅ API Status: {health_data['status'].title()}<br>
            OpenAI Configured: {'✅' if health_data.get('openai_configured') else '❌'}<br>
            Services Ready: {'✅' if health_data.get('services_initialized') else '❌'}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="status-indicator status-unhealthy">
            ❌ API Status: Unavailable<br>
            Error: {health_data.get('error', 'Connection failed')}<br>
            Make sure the FastAPI server is running on {API_BASE_URL}
        </div>
        """, unsafe_allow_html=True)

# ---------- Main App ----------
def main():
    apply_section_styling()
    st.title("🎓 PDF Tutor: Index, Questions & Answer Evaluation")
    st.markdown(f"*Connected to API: {API_BASE_URL}*")
    
    # Check API status
    health_data, is_healthy = check_api_status()
    display_status_indicator(health_data, is_healthy)
    
    if not is_healthy:
        st.error("⚠️ Cannot connect to API backend. Please ensure the FastAPI server is running.")
        st.markdown("**To start the API server, run:** `uvicorn main:app --reload`")
        return
    
    # Upload & index section
    st.markdown('<div class="upload-section">', unsafe_allow_html=True)
    st.markdown('<h3 class="section-header">📁 Upload & Index PDF</h3>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])
    
    if uploaded_file:
        try:
            # Upload file to API
            upload_result = api_client.upload_pdf_from_streamlit(uploaded_file)
            st.success(f"✅ {upload_result['message']}")
            
            default_collection = upload_result['suggested_collection_name']
            collection = st.text_input("Collection name", value=default_collection)
            
            st.markdown('<div class="index-section">', unsafe_allow_html=True)
            if st.button("🚀 Index PDF"):
                try:
                    with st.spinner("Indexing PDF... This may take a moment."):
                        index_result = api_client.index_pdf(uploaded_file.name, collection)
                    st.success(f"✅ {index_result['message']}")
                except Exception as e:
                    st.error(f"❌ Failed to index PDF: {str(e)}")
            st.markdown('</div>', unsafe_allow_html=True)
            
        except Exception as e:
            st.error(f"❌ Failed to upload PDF: {str(e)}")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Question generation & answering section
    st.markdown("---")
    st.markdown('<div class="question-section">', unsafe_allow_html=True)
    st.markdown('<h3 class="section-header">🎯 Practice: Generate Questions and Submit Answers</h3>', unsafe_allow_html=True)
    
    try:
        collections = api_client.list_collections()
        
        if not collections:
            st.info("📚 No vector stores found yet. Index a PDF above first.")
        else:
            chosen = st.selectbox("📋 Choose collection", options=collections)
            n_q = st.number_input("❓ How many questions? (max 10)", min_value=1, max_value=10, value=3, step=1)
            
            if st.button("✨ Generate Questions"):
                try:
                    with st.spinner("Generating questions... Please wait."):
                        questions = api_client.generate_questions(chosen, int(n_q))
                    st.session_state["questions"] = questions
                    st.session_state["current_collection"] = chosen
                except Exception as e:
                    st.error(f"❌ Failed to generate questions: {str(e)}")
            
            if "questions" in st.session_state and st.session_state["questions"]:
                st.markdown("### 📝 Your Questions")
                answers = []
                for idx, q in enumerate(st.session_state["questions"], start=1):
                    st.write(f"**{idx}.** {q}")
                    ans = st.text_area(f"💭 Your answer to Q{idx}", key=f"ans_{idx}")
                    answers.append({"question": q, "answer": ans})
                
                if st.button("📤 Send Answers"):
                    try:
                        with st.spinner("Evaluating your answers... This may take a moment."):
                            results = api_client.evaluate_answers(
                                st.session_state["current_collection"], 
                                answers
                            )
                        
                        # Display results
                        st.markdown('<div class="results-section">', unsafe_allow_html=True)
                        st.markdown('<h3 class="section-header">📊 Evaluation Results</h3>', unsafe_allow_html=True)
                        
                        total_score = 0
                        count = 0
                        
                        for r in results:
                            st.write(f"**❓ Q:** {r['question']}")
                            st.write(f"**✍️ Your Answer:** {r['answer']}")
                            st.write(f"**💡 Ideal Answer (from context):** {r['ideal_answer']}")
                            
                            if r.get("score") is not None:
                                score = r['score']
                                if score >= 8:
                                    st.success(f"🎉 Excellent! You scored {score} out of 10")
                                elif score >= 6:
                                    st.warning(f"👍 Good! You scored {score} out of 10")
                                else:
                                    st.error(f"📚 Needs improvement: {score} out of 10")
                                total_score += score
                                count += 1
                            else:
                                st.warning("⚠️ Score unavailable (evaluation failed)")
                            
                            st.write(f"**🤔 Reasoning:** {r['reasoning']}")
                            st.markdown("---")
                        
                        # Show average
                        if count > 0:
                            avg = round(total_score / count, 2)
                            if avg >= 8:
                                st.balloons()
                                st.success(f"🏆 Outstanding! Average score: {avg} / 10 across {count} question(s)")
                            elif avg >= 6:
                                st.info(f"👏 Well done! Average score: {avg} / 10 across {count} question(s)")
                            else:
                                st.info(f"📈 Keep practicing! Average score: {avg} / 10 across {count} question(s)")
                        
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                    except Exception as e:
                        st.error(f"❌ Failed to evaluate answers: {str(e)}")
    
    except Exception as e:
        st.error(f"❌ Failed to load collections: {str(e)}")
    
    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()