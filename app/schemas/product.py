from typing import Any, List, Optional
from pydantic import BaseModel, Field


class ProductVariantSyncItem(BaseModel):
    productId: str
    variantId: Optional[str] = None
    sku: Optional[str] = None
    name: str
    searchText: str
    categoryId: Optional[str] = None
    categoryName: Optional[str] = None
    brandId: Optional[str] = None
    brandName: Optional[str] = None
    colors: List[str] = Field(default_factory=list)
    sizes: List[str] = Field(default_factory=list)
    material: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    imageKeys: List[str] = Field(default_factory=list)
    status: str = "ACTIVE"
    updatedAt: Optional[str] = None


class ProductSyncRequest(BaseModel):
    variants: List[ProductVariantSyncItem]


class ProductSyncResponse(BaseModel):
    status: str = "success"
    processedCount: int


class ProductVectorVerifyItem(BaseModel):
    productId: str
    variantId: Optional[str] = None


class ProductVectorVerifyRequest(BaseModel):
    items: List[ProductVectorVerifyItem]


class ProductVectorVerifyResult(BaseModel):
    productId: str
    variantId: Optional[str] = None
    present: bool
    pointCount: int = 0


class ProductVectorVerifyResponse(BaseModel):
    items: List[ProductVectorVerifyResult]


class ProductVectorVerifyItem(BaseModel):
    productId: str
    variantId: Optional[str] = None


class ProductVectorVerifyRequest(BaseModel):
    items: List[ProductVectorVerifyItem]


class ProductVectorVerifyResult(BaseModel):
    productId: str
    variantId: Optional[str] = None
    present: bool
    pointCount: int = 0


class ProductVectorVerifyResponse(BaseModel):
    items: List[ProductVectorVerifyResult]
