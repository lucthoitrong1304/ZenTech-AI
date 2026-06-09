from pydantic import BaseModel

class InventoryItemRecommendation(BaseModel):
    productName: str
    variantName: str
    currentStock: int
    averageWeeklySales: float
    suggestedQty: int

class InventoryRecommendRequest(BaseModel):
    items: list[InventoryItemRecommendation]

class InventoryRecommendResponse(BaseModel):
    content: str
