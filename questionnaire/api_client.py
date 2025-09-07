import requests
import streamlit as st
from typing import List, Dict, Any, Optional
from pathlib import Path
import json

class APIClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response and raise appropriate errors"""
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 422:
                error_detail = response.json().get('detail', str(e))
                raise Exception(f"Validation error: {error_detail}")
            elif response.status_code == 404:
                error_detail = response.json().get('error', str(e))
                raise Exception(f"Not found: {error_detail}")
            elif response.status_code >= 500:
                error_detail = response.json().get('error', str(e))
                raise Exception(f"Server error: {error_detail}")
            else:
                error_detail = response.json().get('error', str(e))
                raise Exception(f"API error: {error_detail}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Connection error: {str(e)}")
        except json.JSONDecodeError:
            raise Exception(f"Invalid response format: {response.text}")
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health status"""
        response = self.session.get(f"{self.base_url}/health")
        return self._handle_response(response)
    
    def upload_pdf(self, file_path: Path) -> Dict[str, Any]:
        """Upload a PDF file"""
        with open(file_path, 'rb') as file:
            files = {'file': (file_path.name, file, 'application/pdf')}
            response = self.session.post(f"{self.base_url}/upload-pdf", files=files)
        return self._handle_response(response)
    
    def upload_pdf_from_streamlit(self, uploaded_file) -> Dict[str, Any]:
        """Upload a PDF file from Streamlit file uploader"""
        files = {'file': (uploaded_file.name, uploaded_file.getvalue(), 'application/pdf')}
        response = self.session.post(f"{self.base_url}/upload-pdf", files=files)
        return self._handle_response(response)
    
    def index_pdf(self, filename: str, collection_name: str) -> Dict[str, Any]:
        """Index a PDF file into a vector store"""
        data = {"collection_name": collection_name}
        response = self.session.post(f"{self.base_url}/index-pdf/{filename}", json=data)
        return self._handle_response(response)
    
    def list_collections(self) -> List[str]:
        """List available collections"""
        response = self.session.get(f"{self.base_url}/collections")
        result = self._handle_response(response)
        return result.get("collections", [])
    
    def generate_questions(self, collection_name: str, num_questions: int = 3) -> List[str]:
        """Generate study questions"""
        data = {
            "collection_name": collection_name,
            "num_questions": max(1, min(10, num_questions))
        }
        response = self.session.post(f"{self.base_url}/generate-questions", json=data)
        result = self._handle_response(response)
        return result.get("questions", [])
    
    def evaluate_answers(self, collection_name: str, answers: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Evaluate student answers"""
        data = {
            "collection_name": collection_name,
            "answers": [{"question": qa["question"], "answer": qa["answer"]} for qa in answers]
        }
        response = self.session.post(f"{self.base_url}/evaluate-answers", json=data)
        return self._handle_response(response)

# Create a singleton instance
@st.cache_resource
def get_api_client(base_url: str = "http://localhost:8000") -> APIClient:
    """Get cached API client instance"""
    return APIClient(base_url)