# 🔒 API Security Guide

## Current Security Status

### ❌ **Unsecured Version** (`main.py`)
- **No authentication required**
- **No rate limiting**
- **Open to public access**
- **Suitable for development/testing only**

### ✅ **Secured Version** (`secure_main.py`)
- **API key authentication required**
- **Rate limiting per endpoint**
- **File validation and size limits**
- **Security headers and CORS protection**
- **Usage tracking and monitoring**
- **Security event logging**

## 🔑 Authentication Methods

### **1. API Key Authentication**
Most common for API access:

```bash
# Include in header (recommended)
curl -H "X-API-Key: pdt_your_api_key_here" http://localhost:8000/generate-questions

# Or in query parameter (less secure)
curl "http://localhost:8000/generate-questions?api_key=pdt_your_api_key_here"
```

**Client Integration:**
```python
# Python
headers = {"X-API-Key": "pdt_your_api_key_here"}
response = requests.post(url, headers=headers, json=data)

# Android/Kotlin
val headers = mapOf("X-API-Key" to "pdt_your_api_key_here")

# JavaScript
const headers = {"X-API-Key": "pdt_your_api_key_here"}
fetch(url, {headers, method: "POST", body: JSON.stringify(data)})
```

### **2. JWT Bearer Token Authentication**
For user-based access:

```python
# Login to get token
response = requests.post("/auth/login", json={"username": "user", "password": "pass"})
token = response.json()["access_token"]

# Use token
headers = {"Authorization": f"Bearer {token}"}
```

## 🛡️ Security Features

### **Rate Limiting**
Different limits per endpoint based on cost:

| Endpoint | Rate Limit | Reasoning |
|----------|------------|-----------|
| `/health` | 10/minute | Basic monitoring |
| `/collections` | 20/minute | Lightweight read |
| `/upload-pdf` | 5/minute | File processing |
| `/index-pdf` | 3/minute | AI embedding (expensive) |
| `/generate-questions` | 10/hour | OpenAI API calls |
| `/evaluate-answers` | 5/hour | Most expensive AI operation |

### **File Security**
- **Size limits**: 50MB maximum
- **Type validation**: PDF magic bytes check
- **Content scanning**: Validates actual PDF structure
- **Safe storage**: Files stored in controlled directory

### **Usage Tracking**
Each API call is tracked with different costs:
- Basic operations: 1 point
- File upload: 5 points  
- PDF indexing: 10 points
- Question generation: 1 point per question
- Answer evaluation: 3 points per answer

### **Security Headers**
Automatically added to all responses:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000
```

## ⚙️ Configuration

### **Environment Variables**
```bash
# Required
export OPENAI_API_KEY="your-openai-key"

# Security (recommended)
export JWT_SECRET_KEY="your-secret-key-here"
export API_KEY_0="pdt_your_first_api_key"
export API_KEY_0_NAME="mobile_app"
export API_KEY_1="pdt_your_second_api_key"  
export API_KEY_1_NAME="web_app"

# CORS (production)
export ALLOWED_ORIGINS="https://yourdomain.com,https://app.yourdomain.com"

# Rate limiting (optional)
export REDIS_HOST="localhost"
export REDIS_PORT="6379"

# Development mode
export DEVELOPMENT="true"  # Enables demo API key
```

### **API Key Management**
```python
from security import api_key_manager

# Generate new key
new_key = api_key_manager.generate_key("client_name")
print(f"New API key: {new_key}")

# Validate key
key_info = api_key_manager.validate_key("pdt_existing_key")
if key_info:
    print(f"Valid key for: {key_info['name']}")
```

## 🚀 Deployment Security

### **Development Setup**
```bash
# Use unsecured version for development
python main.py  # or: uvicorn main:app --reload

# Demo API key automatically created when DEVELOPMENT=true
```

### **Production Setup**
```bash
# Use secured version for production
export DEVELOPMENT="false"
export API_KEY_0="pdt_$(openssl rand -base64 32)"
export ALLOWED_ORIGINS="https://yourdomain.com"

python secure_main.py  # or: uvicorn secure_main:app
```

### **Docker Security**
```dockerfile
FROM python:3.11-slim

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
WORKDIR /app
USER app

# Install dependencies
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Copy code
COPY --chown=app:app . .

# Run secured version
CMD ["python", "secure_main.py"]
```

## 📊 Monitoring & Logging

### **Security Events**
All security events are logged:
```python
# Examples of logged events
"file_upload": {"api_key": "mobile_app", "filename": "textbook.pdf"}
"questions_generated": {"api_key": "web_app", "collection": "math", "num_questions": 5}
"rate_limit_exceeded": {"api_key": "suspicious_key", "endpoint": "/generate-questions"}
```

### **Usage Monitoring**
```bash
# Check API key usage
curl -H "X-API-Key: admin_key" http://localhost:8000/admin/usage/pdt_client_key

# Response:
{
  "api_key": "pdt_client_key",
  "usage": {
    "total_requests": 150,
    "endpoints": {
      "generate_questions": 45,
      "evaluate_answers": 30
    },
    "first_request": "2024-01-01T10:00:00",
    "last_request": "2024-01-01T15:30:00"
  }
}
```

## 🔧 Client Security Best Practices

### **Mobile Apps**
```kotlin
// Store API keys securely
class SecureStorage {
    companion object {
        private const val KEYSTORE_ALIAS = "pdf_tutor_key"
        
        fun storeApiKey(context: Context, apiKey: String) {
            // Use Android Keystore or encrypted SharedPreferences
        }
        
        fun getApiKey(context: Context): String? {
            // Retrieve from secure storage
        }
    }
}
```

### **Web Apps**
```javascript
// Never store API keys in frontend code
// Use backend proxy instead
const apiCall = async (endpoint, data) => {
    // Call your backend, which then calls PDF Tutor API
    return fetch(`/api/proxy${endpoint}`, {
        method: 'POST',
        credentials: 'include',  // Include session cookies
        body: JSON.stringify(data)
    });
};
```

### **Server-to-Server**
```python
# Use environment variables
import os
api_key = os.getenv("PDF_TUTOR_API_KEY")

# Implement retry logic for rate limits
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        backoff_factor=1
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
```

## 🚨 Security Recommendations

### **For Development:**
1. Use `main.py` (unsecured) for local development
2. Set `DEVELOPMENT=true` for demo API key
3. Use localhost CORS origins

### **For Production:**
1. **Always use `secure_main.py`**
2. **Generate strong API keys** 
3. **Set restrictive CORS origins**
4. **Enable HTTPS with SSL certificates**
5. **Use Redis for distributed rate limiting**
6. **Monitor security logs regularly**
7. **Implement API key rotation**
8. **Set up alerts for suspicious activity**

### **Network Security:**
```bash
# Use reverse proxy (nginx)
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 🔍 Security Checklist

- [ ] API keys configured and secured
- [ ] Rate limiting enabled  
- [ ] CORS origins restricted
- [ ] HTTPS enabled in production
- [ ] Security headers configured
- [ ] File validation implemented
- [ ] Usage monitoring active
- [ ] Security logging enabled
- [ ] Error handling prevents info leakage
- [ ] Regular security audits scheduled

**Remember**: Security is a process, not a one-time setup. Regular reviews and updates are essential! 🔒