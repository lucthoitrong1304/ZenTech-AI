import logging
import os
from fastapi import FastAPI

from app.api.routes import router

def setup_logging() -> None:
    # Thư mục log lưu tương đối từ thư mục dự án ZenTech-AI sang docker/logs
    log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docker", "logs"))
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "ai.log")

    # Tạo FileHandler ghi nhận log dạng UTF-8
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)

    # Format log tương thích với regex bóc tách của Java LokiService
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] - %(message)s")
    file_handler.setFormatter(formatter)

    # Cấu hình root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)

    # Điều hướng uvicorn loggers sang ghi file luôn
    for uvicorn_logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(uvicorn_logger_name)
        uvicorn_logger.addHandler(file_handler)

def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI()
    app.include_router(router)
    return app


app = create_app()
