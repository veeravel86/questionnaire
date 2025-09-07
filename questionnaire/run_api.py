#!/usr/bin/env python3
"""
Convenience script to run the PDF Tutor API server
"""
import os
import sys
import uvicorn
from pathlib import Path

def main():
    """Run the FastAPI server"""
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY environment variable not set!")
        print("   The API will start but AI features will not work.")
        print("   Set your key with: export OPENAI_API_KEY='your-key-here'")
        print()
    
    # Check if we're in the right directory
    if not Path("main.py").exists():
        print("❌ Error: main.py not found in current directory")
        print("   Please run this script from the questionnaire directory")
        sys.exit(1)
    
    print("🚀 Starting PDF Tutor API Server...")
    print("📚 API Documentation will be available at:")
    print("   • Interactive docs: http://localhost:8000/docs")
    print("   • ReDoc: http://localhost:8000/redoc")
    print()
    print("🎓 To start the Streamlit frontend, run in another terminal:")
    print("   streamlit run streamlit_app.py")
    print()
    print("Press Ctrl+C to stop the server")
    print("-" * 50)
    
    try:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            reload_dirs=[".", "services"],
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 PDF Tutor API Server stopped")
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()