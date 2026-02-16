
import logging
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("api_logger")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Configure app logger as well so other modules get logging
from logging import getLogger, StreamHandler, DEBUG, INFO, Formatter
import sys

# Crucial: Configure root logger to catch everything
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Check if handler already exists to avoid duplicates
if not root_logger.handlers:
    handler = StreamHandler(sys.stdout)
    handler.setFormatter(Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    root_logger.addHandler(handler)

# Specific loggers for our app
app_logger = logging.getLogger("app")
app_logger.setLevel(logging.INFO)

# Ensure api_logger also works
logger = logging.getLogger("api_logger")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(handler)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log Request
        # content_type = request.headers.get('content-type', '')
        # if "multipart/form-data" not in content_type:
        #      try:
        #         body = await request.body()
        #         logger.debug(f"Body: {body.decode('utf-8')[:1000]}") # Truncate
        #      except Exception:
        #         logger.debug("Body: <binary or non-utf8 content>")

        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            raise e
            
        process_time = time.time() - start_time
        logger.info(f"RESPONSE: {response.status_code} (took {process_time:.4f}s)")
        
        return response
