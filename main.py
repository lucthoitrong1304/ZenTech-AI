import logging
import os
import shutil
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
            logger.error(f"Request failed: {request.method} {request.url.path} - Lỗi: {str(exc)} - Thời gian xử lý: {duration_ms:.2f}ms", exc_info=True)
            raise exc
        finally:
            trace_id_var.reset(token)

from logging.handlers import TimedRotatingFileHandler

class ArchivedTimedRotatingFileHandler(TimedRotatingFileHandler):
    def rotation_filename(self, default_name: str) -> str:
        # default_name looks like: .../docker/logs/ai.log.YYYY-MM-DD
        base_dir, file_name = os.path.split(default_name)
        parts = file_name.split('.')
        # parts: ['ai', 'log', 'YYYY-MM-DD']
        if len(parts) >= 3:
            date_str = parts[2]
            archive_dir = os.path.join(base_dir, "archived")
            os.makedirs(archive_dir, exist_ok=True)
            return os.path.join(archive_dir, f"ai-{date_str}.log")
        return default_name

    def rotate(self, source: str, dest: str) -> None:
        if not os.path.exists(source):
            return

        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            if os.path.exists(dest):
                os.remove(dest)
            os.rename(source, dest)
        except PermissionError:
            self._copy_truncate_when_locked(source, dest)

    def _copy_truncate_when_locked(self, source: str, dest: str) -> None:
        fallback_dest = self._next_available_archive_name(dest)
        try:
            shutil.copy2(source, fallback_dest)
            with open(source, "w", encoding=self.encoding or "utf-8"):
                pass
        except OSError:
            # Windows can keep ai.log locked when another process tails or writes it.
            # Keep the app running and defer rotation to a later restart/rollover.
            return

    def _next_available_archive_name(self, dest: str) -> str:
        if not os.path.exists(dest):
            return dest

        index = 1
        while True:
            candidate = f"{dest}.{index}"
            if not os.path.exists(candidate):
                return candidate
            index += 1

def setup_logging() -> None:
    # Thư mục log lưu tương đối từ thư mục dự án ZenTech-AI sang docker/logs
    log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docker", "logs"))
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "ai.log")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    file_handler = next(
        (
            handler
            for handler in root_logger.handlers
            if isinstance(handler, ArchivedTimedRotatingFileHandler)
            and getattr(handler, "baseFilename", None) == log_file
        ),
        None,
    )

    if file_handler is None:
        file_handler = ArchivedTimedRotatingFileHandler(
            log_file,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        root_logger.addHandler(file_handler)

    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] [%(trace_id)s] - %(message)s")
    )

    if not any(isinstance(log_filter, TraceIdFilter) for log_filter in file_handler.filters):
        file_handler.addFilter(TraceIdFilter())

    ai_logger = logging.getLogger("ai-service")
    ai_logger.setLevel(logging.INFO)
    ai_logger.propagate = True

    for uvicorn_logger_name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(uvicorn_logger_name)
        uvicorn_logger.setLevel(logging.INFO)
        # Write through the root file handler only. Attaching the same handler here
        # and propagating to root would persist every Uvicorn event twice.
        if file_handler in uvicorn_logger.handlers:
            uvicorn_logger.removeHandler(file_handler)
        uvicorn_logger.propagate = True

    access_logger = logging.getLogger("uvicorn.access")
    access_logger.setLevel(logging.WARNING)
    if file_handler in access_logger.handlers:
        access_logger.removeHandler(file_handler)

    for noisy_logger_name in ("httpx", "httpcore", "openai"):
        logging.getLogger(noisy_logger_name).setLevel(logging.WARNING)

def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)
    app.include_router(router)
    return app

app = create_app()
