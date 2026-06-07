from pydantic import BaseModel

class ReportAnalyzeRequest(BaseModel):
    category: str
    data: str

class ReportAnalyzeResponse(BaseModel):
    content: str
