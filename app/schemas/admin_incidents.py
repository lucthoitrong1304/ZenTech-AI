from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class IncidentInfo(BaseModel):
    code: str
    service_name: str
    api_path: str
    http_method: str
    status_code: int
    error_message: str
    stack_trace: str
    severity: str

class IncidentAnalyzeRequest(BaseModel):
    incident: IncidentInfo
    logs: List[str]
    activity_logs: List[Dict[str, Any]]

class IncidentAnalyzeResponse(BaseModel):
    summary: str
    root_cause: str
    severity_suggestion: str
    solution_suggestion: str
    confidence_score: float
