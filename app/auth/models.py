"""JWT Payload Models"""
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime


class JWTPayload(BaseModel):
    """JWT token payload extracted from Keycloak"""
    user_id: UUID = Field(..., alias="sub")
    org_id: str
    tenant_schema: str
    roles: list[str] = []
    permissions: list[str] = []
    iat: Optional[datetime] = None
    exp: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
