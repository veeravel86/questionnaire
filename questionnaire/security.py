"""
Security middleware and utilities for PDF Tutor API
"""
import os
import time
import hashlib
import secrets
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from jose import JWTError, jwt
import redis
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


# ---------- Configuration ----------
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
API_KEY_PREFIX = "pdt_"  # PDF Tutor API key prefix

# Rate limiting storage
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True
    )
    # Test connection
    redis_client.ping()
    print("✅ Redis connected for rate limiting")
except Exception:
    print("⚠️ Redis not available, using memory-based rate limiting")
    redis_client = None

# Rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', 6379)}" if redis_client else "memory://",
    default_limits=["100/hour"]
)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token security
security = HTTPBearer(auto_error=False)


# ---------- API Key Management ----------
class APIKeyManager:
    def __init__(self):
        self.api_keys = self._load_api_keys()
    
    def _load_api_keys(self) -> Dict[str, Dict[str, Any]]:
        """Load API keys from environment or database"""
        keys = {}
        
        # Load from environment variables
        for i in range(10):  # Support up to 10 API keys
            key = os.getenv(f"API_KEY_{i}")
            name = os.getenv(f"API_KEY_{i}_NAME", f"client_{i}")
            if key:
                keys[key] = {
                    "name": name,
                    "created_at": datetime.now(),
                    "usage_count": 0,
                    "rate_limit": "50/hour"  # Per-key rate limit
                }
        
        # Demo key for development
        if not keys and os.getenv("DEVELOPMENT") == "true":
            demo_key = f"{API_KEY_PREFIX}demo_12345"
            keys[demo_key] = {
                "name": "development",
                "created_at": datetime.now(),
                "usage_count": 0,
                "rate_limit": "100/hour"
            }
            print(f"🔑 Development API key: {demo_key}")
        
        return keys
    
    def validate_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Validate API key and return key info"""
        if api_key in self.api_keys:
            self.api_keys[api_key]["usage_count"] += 1
            return self.api_keys[api_key]
        return None
    
    def generate_key(self, name: str) -> str:
        """Generate new API key"""
        key = f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"
        self.api_keys[key] = {
            "name": name,
            "created_at": datetime.now(),
            "usage_count": 0,
            "rate_limit": "50/hour"
        }
        return key


api_key_manager = APIKeyManager()


# ---------- Authentication Functions ----------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


# ---------- Security Dependencies ----------
def get_api_key(request: Request) -> Optional[str]:
    """Extract API key from request"""
    # Check header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return api_key
    
    # Check query parameter (less secure)
    api_key = request.query_params.get("api_key")
    if api_key:
        return api_key
    
    return None


def verify_api_key(request: Request) -> Dict[str, Any]:
    """Verify API key dependency"""
    api_key = get_api_key(request)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Include 'X-API-Key' header or 'api_key' query parameter."
        )
    
    key_info = api_key_manager.validate_key(api_key)
    if not key_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return key_info


def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Verify JWT token dependency"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required"
        )
    
    token_data = verify_token(credentials.credentials)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    return token_data


# ---------- Security Middleware ----------
async def security_headers_middleware(request: Request, call_next):
    """Add security headers to responses"""
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY" 
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    return response


def check_file_size(file_size: int, max_size_mb: int = 50):
    """Check if uploaded file size is within limits"""
    max_size = max_size_mb * 1024 * 1024  # Convert to bytes
    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {max_size_mb}MB"
        )


def validate_file_content(file_content: bytes) -> bool:
    """Validate that file is actually a PDF"""
    # Check PDF magic bytes
    pdf_signature = b'%PDF-'
    return file_content.startswith(pdf_signature)


# ---------- Usage Tracking ----------
class UsageTracker:
    def __init__(self):
        self.usage = {}
    
    def track_request(self, api_key: str, endpoint: str, cost: int = 1):
        """Track API usage"""
        if api_key not in self.usage:
            self.usage[api_key] = {
                "total_requests": 0,
                "endpoints": {},
                "first_request": datetime.now(),
                "last_request": datetime.now()
            }
        
        self.usage[api_key]["total_requests"] += cost
        self.usage[api_key]["last_request"] = datetime.now()
        
        if endpoint not in self.usage[api_key]["endpoints"]:
            self.usage[api_key]["endpoints"][endpoint] = 0
        self.usage[api_key]["endpoints"][endpoint] += cost
    
    def get_usage(self, api_key: str) -> Dict[str, Any]:
        """Get usage statistics for API key"""
        return self.usage.get(api_key, {})


usage_tracker = UsageTracker()


# ---------- Custom Exceptions ----------
class SecurityException(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# ---------- Helper Functions ----------
def hash_password(password: str) -> str:
    """Hash password for storage"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def generate_csrf_token() -> str:
    """Generate CSRF token"""
    return secrets.token_urlsafe(32)


def log_security_event(event_type: str, details: Dict[str, Any]):
    """Log security events"""
    timestamp = datetime.now().isoformat()
    print(f"🔒 [{timestamp}] SECURITY: {event_type} - {details}")


# ---------- Rate Limiting Helpers ----------
def get_rate_limit_key(request: Request, api_key: str = None) -> str:
    """Generate rate limit key"""
    if api_key:
        return f"api_key:{api_key}"
    return f"ip:{get_remote_address(request)}"


def check_rate_limit(request: Request, api_key: str = None, limit: str = "10/minute"):
    """Check if request exceeds rate limit"""
    key = get_rate_limit_key(request, api_key)
    # Implementation would depend on chosen rate limiting library
    # This is a placeholder for the concept
    pass