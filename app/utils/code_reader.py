import re
import os
import logging

logger = logging.getLogger("ai-service.code-reader")

# Bản đồ ánh xạ thư mục dự án dựa trên tên dịch vụ
PROJECT_DIRS_MAP = {
    "FRONTEND": r"d:\1. HCMUTE\KLTN\ZenTech-FE",
    "BACKEND": r"d:\1. HCMUTE\KLTN\ZenTech",
    "AI-SERVICE": r"d:\1. HCMUTE\KLTN\ZenTech-AI",
}

def get_project_dir_by_service(service_name: str) -> str:
    """
    Trả về đường dẫn thư mục dự án tương ứng với service name.
    """
    if not service_name:
        return PROJECT_DIRS_MAP["BACKEND"]
        
    s_upper = service_name.upper()
    if "FE" in s_upper or "FRONTEND" in s_upper or "ANGULAR" in s_upper or "REACT" in s_upper:
        return PROJECT_DIRS_MAP["FRONTEND"]
    elif "AI" in s_upper or "FASTAPI" in s_upper or "PYTHON" in s_upper:
        return PROJECT_DIRS_MAP["AI-SERVICE"]
    else:
        # Mặc định là Spring Boot backend
        return PROJECT_DIRS_MAP["BACKEND"]

def extract_all_file_lines(text: str):
    """
    Tìm tất cả các cặp (tên_file, dòng_lỗi) xuất hiện trong text/stack trace.
    Trả về danh sách tuple [(file_name, line_number), ...]
    """
    if not text:
        return []
        
    results = []
    
    # 1. Quét tìm log format của Python: File "path/to/file.py", line 42
    py_matches = re.findall(r'File "([^"]+)", line (\d+)', text)
    for path, line in py_matches:
        results.append((os.path.basename(path), int(line)))
        
    # 2. Quét tìm log format của Java/TypeScript: (FileName.java:42) hoặc FileName.ts:42
    general_matches = re.findall(r"([\w-]+\.(?:java|kt|py|ts|js|tsx|jsx)):(\d+)", text)
    for file_name, line in general_matches:
        results.append((file_name, int(line)))
        
    return results

def find_file_in_dir(project_dir: str, file_name: str) -> str:
    """
    Tìm kiếm đường dẫn tuyệt đối của file_name trong thư mục project_dir.
    Tránh tìm trong các thư mục build/libraries/node_modules/venv.
    """
    ignored_dirs = {".git", ".venv", "node_modules", "target", "build", ".idea", "dist"}
    
    for root, dirs, files in os.walk(project_dir):
        # Loại bỏ các thư mục không muốn duyệt để tăng tốc độ tìm kiếm
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        
        if file_name in files:
            return os.path.join(root, file_name)
            
    return None

def get_code_context_from_file(file_path: str, target_line: int, context_lines: int = 15) -> str:
    """
    Đọc nội dung file xung quanh dòng bị lỗi.
    """
    try:
        if not os.path.exists(file_path):
            return ""
            
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            
        total_lines = len(lines)
        # line_number trong stack trace là 1-indexed
        start = max(0, target_line - context_lines - 1)
        end = min(total_lines, target_line + context_lines)
        
        context_code = []
        for i in range(start, end):
            line_num = i + 1
            marker = ">>> " if line_num == target_line else "    "
            context_code.append(f"{marker}{line_num:4d} | {lines[i]}")
            
        return "".join(context_code)
    except Exception as e:
        logger.error("Lỗi khi đọc file %s: %s", file_path, str(e))
        return f"Lỗi đọc file: {str(e)}"

def get_code_context_from_stack_trace(service_name: str, stack_trace: str, context_lines: int = 15) -> str:
    """
    Hàm tổng hợp: Nhận vào service_name và stack trace, tìm file code thực tế và đọc context.
    """
    project_dir = get_project_dir_by_service(service_name)
    file_lines = extract_all_file_lines(stack_trace)
    
    if not file_lines:
        logger.warning("Không tìm thấy mẫu file:line nào trong stack trace.")
        return ""
        
    logger.info("Tìm thấy các cặp file:line trong stack trace: %s", file_lines)
    
    # Duyệt từ trên xuống (hoặc từ dưới lên) để tìm file thực tế tồn tại trong repo của ta
    for file_name, line_number in file_lines:
        file_path = find_file_in_dir(project_dir, file_name)
        if file_path:
            logger.info("Đã tìm thấy file %s tại %s", file_name, file_path)
            context = get_code_context_from_file(file_path, line_number, context_lines)
            if context:
                # Trả về kèm đường dẫn tương đối để AI dễ nhận biết
                rel_path = os.path.relpath(file_path, project_dir)
                return (
                    f"--- SOURCE CODE CONTEXT ({rel_path} - Line {line_number}) ---\n"
                    f"{context}\n"
                    f"--- END SOURCE CODE CONTEXT ---\n"
                )
                
    logger.warning("Không tìm thấy file nào từ stack trace tồn tại trong thư mục %s", project_dir)
    return ""
