import logging
import os
import time
import uuid
import contextvars
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api.routes import router

# Context variable to hold the trace ID during the request lifecycle
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")

class TraceIdFilter(logging.Filter):
    """
    Injects the request trace_id from contextvars into the log record.
    If no trace_id is present, it uses a default placeholder.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get() or "ZT-AI-SYSTEM"
        return True

class LoggingMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that intercepts all incoming HTTP requests to log them globally.
    Extracts the X-Trace-Id header or generates a new one, logs request start and end (with duration),
    and appends the trace ID to the response header.
    """
    async def dispatch(self, request: Request, call_next):
        # 1. Extract trace ID from header or generate a new one
        trace_id = request.headers.get("X-Trace-Id")
        if not trace_id or not trace_id.strip():
            trace_id = f"ZT-AI-{uuid.uuid4().hex[:8].upper()}"
        else:
            trace_id = trace_id.strip()

        # 2. Store trace ID in contextvar
        token = trace_id_var.set(trace_id)
        
        # 3. Log request start
        logger = logging.getLogger("ai-service")
        
        # Skip verbose logging for health checks to keep logs cleaner
        is_health_check = request.url.path in ("/health", "/")
        
        if not is_health_check:
            logger.info(f"Incoming Request: {request.method} {request.url.path}")

        start_time = time.time()
        try:
            response: Response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            
            if not is_health_check:
                logger.info(f"Outgoing Response: {response.status_code} cho {request.method} {request.url.path} - Thời gian xử lý: {duration_ms:.2f}ms")
            
            response.headers["X-Trace-Id"] = trace_id
            return response
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Request failed: {request.method} {request.url.path} - Lỗi: {str(exc)} - Thời gian xử lý: {duration_ms:.2f}ms")
            raise exc
        finally:
            trace_id_var.reset(token)

def setup_logging() -> None:
    # Thư mục log lưu tương đối từ thư mục dự án ZenTech-AI sang docker/logs
    log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docker", "logs"))
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "ai.log")

    # Tạo FileHandler ghi nhận log dạng UTF-8
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)

    # Format log tương thích với regex bóc tách của Java LokiService
    # Bổ dung [%(trace_id)s] để khớp với regex bóc tách traceId
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] [%(trace_id)s] - %(message)s")
    file_handler.setFormatter(formatter)
    
    # Gán filter để tiêm trace_id từ contextvars
    trace_filter = TraceIdFilter()
    file_handler.addFilter(trace_filter)

    # Cấu hình root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)

    # Điều hướng uvicorn loggers sang ghi file luôn
    for uvicorn_logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(uvicorn_logger_name)
        uvicorn_logger.addHandler(file_handler)

def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)
    app.include_router(router)
    return app

app = create_app()
