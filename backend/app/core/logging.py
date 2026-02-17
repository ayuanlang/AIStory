
import logging
import time
import re
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError
from app.core.config import settings

# Configure standard loggers to be less noisy
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.ERROR)
logging.getLogger("fastapi").setLevel(logging.WARNING)

logger = logging.getLogger("functional_activity")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
logger.addHandler(handler)

# Map Regex Patterns to Functional Names (Comprehensive)
FUNCTION_MAP = [
    # Auth
    (r"POST /api/v1/login.*", "User Login"),
    (r"POST /api/v1/register.*", "User Registration"),
    
    # Projects
    (r"GET /api/v1/projects$", "View Project List"),
    (r"POST /api/v1/projects$", "Create New Project"),
    (r"GET /api/v1/projects/\d+$", "View Project Details"),
    (r"PUT /api/v1/projects/\d+$", "Update Project"),
    (r"DELETE /api/v1/projects/\d+$", "Delete Project"),
    
    # Episodes & Script
    (r"GET /api/v1/projects/\d+/episodes", "View Episodes List"),
    (r"POST /api/v1/projects/\d+/episodes", "Create Episode"),
    (r"PUT /api/v1/episodes/\d+/segments", "Update Script Segments"),
    (r"GET /api/v1/episodes/\d+/scenes", "View Scenes List"),
    
    # AI Generation & Analysis
    (r"POST /api/v1/analyze_scene", "Function: AI Scene Analysis"),
    (r"POST /api/v1/scenes/\d+/ai_generate_visuals", "Function: AI Visual Generation"),
    (r"POST /api/v1/scenes/\d+/ai_generate_beats", "Function: AI Beat Generation"),
    (r"POST /api/v1/scenes/\d+/ai_generate_shots", "Function: AI Shot Generation"),
    (r"POST /api/v1/scenes/\d+/apply_ai_result", "Function: Apply AI Result"),
    
    # Agent
    (r"POST /api/v1/agent/command", "Function: Agent Command"),
    
    # Tools
    (r"POST /api/v1/tools/translate", "Tool: Translate"),
    (r"POST /api/v1/tools/refine_prompt", "Tool: Refine Prompt"),
    
    # Assets
    (r"POST /api/v1/assets/upload", "Upload Asset"),
    (r"GET /api/v1/assets", "View Assets Library"),
    (r"DELETE /api/v1/assets/\d+", "Delete Asset"),
    
    # Users & Admin
    (r"GET /api/v1/users/me", "Get Current User Info"),
    (r"GET /api/v1/users$", "Admin: View All Users"),
    (r"PUT /api/v1/users/\d+/credits", "Admin: Update User Credits"),
    
    # Billing & Recharge - SPECIFIC REQUEST
    # (r"GET /api/v1/billing/recharge/status/.*", "Check Recharge Status"), # Removed to reduce log spam during polling
    (r"POST /api/v1/billing/recharge/create", "Initiate Recharge Order"),
    (r"POST /api/v1/billing/recharge/mock_pay/.*", "Mock Payment Execution"),
    (r"GET /api/v1/billing/recharge/plans", "View Recharge Plans"),
    (r"GET /api/v1/billing/transactions", "View Transaction History"),
    (r"GET /api/v1/billing/rules", "View Pricing Rules"),
    
    # System
    (r"GET /api/v1/system/logs", "Admin: View System Logs"),
    (r"GET /admin/payment-config", "Admin: View Payment Config"),
    (r"POST /admin/payment-config", "Admin: Update Payment Config"),
]

def get_function_name(method: str, path: str):
    key = f"{method} {path}"
    for pattern, name in FUNCTION_MAP:
        if re.search(pattern, key):
            return name
    return None

def get_user_from_token(auth_header: str):
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub") # format return as needed
    except JWTError:
        return None

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # 1. Identify Function
        method = request.method
        path = request.url.path
        func_name = get_function_name(method, path)
        
        # 2. Extract Client Info
        client_host = request.client.host if request.client else "unknown"
        
        # 3. Extract User (Best Effort)
        username = "Guest"
        auth = request.headers.get("Authorization")
        if auth:
            user = get_user_from_token(auth)
            if user:
                username = user

        response = await call_next(request)
        process_time = time.time() - start_time
        
        # 4. Log meaningful events
        if func_name:
            if 200 <= response.status_code < 300:
                 logger.info(f"Functional Access | User: {username} | Action: {func_name} | IP: {client_host} | Time: {process_time:.2f}s")
            else:
                 logger.warning(f"Functional Alert | User: {username} | Action: {func_name} | Status: {response.status_code} | IP: {client_host}")
        
        # 5. Fallback for unmapped but important errors (500s)
        elif response.status_code >= 500:
             logger.error(f"System Error | User: {username} | Path: {method} {path} | Status: {response.status_code}")

        return response
