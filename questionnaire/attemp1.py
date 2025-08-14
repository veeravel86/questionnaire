import os
from pathlib import Path
import streamlit as st

# Loaders & vector store
from langchain_community.document_loaders import PyPDFLoader
try:
    # Optional, better with encrypted/complex PDFs
    from langchain_community.document_loaders import PyMuPDFLoader  # requires: pip install pymupdf
    HAS_PYMUPDF = True
except Exception:
    HAS_PYMUPDF = False

from pypdf.errors import DependencyError as PdfDependencyError
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

# (Agent-related imports kept but not used while we test indexing only)
# from langchain_openai import ChatOpenAI
# from langchain.agents import initialize_agent, Tool, AgentType

# ---------- Paths ----------
APP_DIR = Path(__file__).parent if "__file__" in globals() else Path.cwd()
DB_DIR = APP_DIR / "vectorstores"
DB_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = APP_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# ---------- API Key ----------
if not os.getenv("OPENAI_API_KEY"):
    st.warning("OPENAI_API_KEY not set. Embeddings will fail. Set it before indexing.")

embeddings = OpenAIEmbeddings()

# ---------- Indexing Logic (robust, with fallbacks) ----------

def _load_pdf_docs(abs_path: Path):
    """Try PyPDF first; if AES/cryptography error, suggest installing cryptography or fall back to PyMuPDF if available."""
    try:
        return PyPDFLoader(str(abs_path)).load()
    except PdfDependencyError:
        # AES encryption encountered, cryptography not installed
        if HAS_PYMUPDF:
            st.info("PyPDF needs 'cryptography' for AES. Falling back to PyMuPDF loader…")
            return PyMuPDFLoader(str(abs_path)).load()
        else:
            st.error(
                "This PDF appears to use AES encryption. Install 'cryptography' (pip install cryptography) "
                "or install 'pymupdf' for fallback (pip install pymupdf)."
            )
            raise
    except Exception as e:
        # Other parsing issues → try PyMuPDF if available
        if HAS_PYMUPDF:
            st.info(f"PyPDF failed with: {e}. Trying PyMuPDF loader…")
            return PyMuPDFLoader(str(abs_path)).load()
        raise


def index_pdf(file_path: Path, collection_name: str) -> str:
    # sanitize & resolve absolute path
    abs_path = Path(str(file_path).strip().strip("'\" ")).resolve()
    if not abs_path.exists():
        raise FileNotFoundError(f"PDF file not found at {abs_path}")

    # Load
    docs = _load_pdf_docs(abs_path)

    # Chunk
    splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=120)
    chunks = splitter.split_documents(docs)

    # Embed & persist FAISS
    vs = FAISS.from_documents(chunks, embedding=embeddings)
    vs.save_local(str(DB_DIR / collection_name))

    return f"✅ Indexed '{abs_path.name}' into collection '{collection_name}' at {DB_DIR / collection_name}"

# ---------- Streamlit UI (indexing only) ----------
st.title("PDF Indexing Test – Robust Loader & Absolute Paths")

pdf = st.file_uploader("Upload a PDF", type=["pdf"])

if pdf:
    # Save upload
    saved_path = (UPLOAD_DIR / pdf.name).resolve()
    with open(saved_path, "wb") as f:
        f.write(pdf.getbuffer())

    st.success(f"Saved: {saved_path}")

    # Choose collection name
    default_collection = pdf.name.rsplit(".pdf", 1)[0]
    collection = st.text_input("Collection name", value=default_collection)

    # Debug aids
    with st.expander("Debug info"):
        st.write({
            "APP_DIR": str(APP_DIR),
            "UPLOAD_DIR": str(UPLOAD_DIR),
            "DB_DIR": str(DB_DIR),
            "saved_path_exists": saved_path.exists(),
        })

    if st.button("Index PDF"):
        try:
            msg = index_pdf(saved_path, collection)
            st.success(msg)
        except Exception as e:
            st.exception(e)

# Notes for later: re-enable tools/agent once indexing is verified.
# from langchain_openai import ChatOpenAI
# from langchain.agents import initialize_agent, Tool, AgentType
# tool = Tool(name="Index PDF", func=lambda x: index_pdf(Path(x), collection), description="Index PDF into FAISS")
# agent = initialize_agent([tool], ChatOpenAI(model="gpt-4o", temperature=0), agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION)
# agent.run(f"Index PDF with {saved_path}")
