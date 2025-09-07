import os
from pathlib import Path
from pypdf.errors import DependencyError as PdfDependencyError

from langchain_community.document_loaders import PyPDFLoader
try:
    from langchain_community.document_loaders import PyMuPDFLoader
    HAS_PYMUPDF = True
except Exception:
    HAS_PYMUPDF = False

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings


class PDFService:
    def __init__(self, db_dir: Path, embeddings: OpenAIEmbeddings = None):
        self.db_dir = db_dir
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.embeddings = embeddings or OpenAIEmbeddings()
    
    def _load_pdf_docs(self, abs_path: Path):
        """Load PDF documents with fallback to PyMuPDF if needed."""
        try:
            return PyPDFLoader(str(abs_path)).load()
        except PdfDependencyError:
            if HAS_PYMUPDF:
                return PyMuPDFLoader(str(abs_path)).load()
            else:
                raise Exception("This PDF appears to use AES encryption. Install 'cryptography' or 'pymupdf'.")
        except Exception as e:
            if HAS_PYMUPDF:
                return PyMuPDFLoader(str(abs_path)).load()
            raise
    
    def index_pdf(self, file_path: Path, collection_name: str) -> str:
        """Index a PDF file into a vector store collection."""
        abs_path = Path(str(file_path).strip().strip("'\" ")).resolve()
        if not abs_path.exists():
            raise FileNotFoundError(f"PDF file not found at {abs_path}")

        docs = self._load_pdf_docs(abs_path)
        splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=120)
        chunks = splitter.split_documents(docs)

        vs = FAISS.from_documents(chunks, embedding=self.embeddings)
        vs.save_local(str(self.db_dir / collection_name))

        return f"Indexed '{abs_path.name}' into collection '{collection_name}' at {self.db_dir / collection_name}"
    
    def list_collections(self) -> list:
        """List available vector store collections."""
        if not self.db_dir.exists():
            return []
        return [
            p.name for p in self.db_dir.iterdir() 
            if p.is_dir() and ((p / "index.faiss").exists() or any(p.glob("*.faiss")))
        ]
    
    def load_vectorstore(self, collection_name: str) -> FAISS:
        """Load a vector store by collection name."""
        store_dir = self.db_dir / collection_name
        if not store_dir.exists():
            raise FileNotFoundError(f"No vector store for '{collection_name}'.")
        return FAISS.load_local(str(store_dir), self.embeddings, allow_dangerous_deserialization=True)