from pydantic import BaseModel, Field

class ManagementImpactAnalyzeRequest(BaseModel):
    incidentCode: str = Field(..., description="Mã sự cố, ví dụ: INC-0001")
    serviceName: str = Field(..., description="Tên dịch vụ bị lỗi")
    apiPath: str = Field(..., description="Đường dẫn API gặp lỗi")
    httpMethod: str = Field(..., description="Phương thức HTTP (GET, POST, ...)")
    statusCode: int = Field(..., description="Mã trạng thái HTTP lỗi")
    durationMinutes: int = Field(..., description="Thời gian diễn ra sự cố tính theo phút")
    actualRevenue: float = Field(..., description="Doanh thu thực tế trong thời gian lỗi")
    expectedRevenue: float = Field(..., description="Doanh thu kỳ vọng (baseline) trong thời gian lỗi")
    revenueLoss: float = Field(..., description="Doanh thu thất thoát")
    actualOrders: int = Field(..., description="Số đơn hàng đặt thành công")
    expectedOrders: int = Field(..., description="Số đơn hàng kỳ vọng đặt thành công")
    lostOrders: int = Field(..., description="Số đơn hàng bị mất")
    affectedUsers: int = Field(..., description="Số lượng khách hàng bị ảnh hưởng")
    severity: str = Field(..., description="Mức độ nghiêm trọng được phân loại (LOW, MEDIUM, HIGH, CRITICAL)")

class ManagementImpactAnalyzeResponse(BaseModel):
    aiSummary: str = Field(..., description="Báo cáo diễn giải và khuyến nghị từ AI bằng tiếng Việt (định dạng Markdown)")
