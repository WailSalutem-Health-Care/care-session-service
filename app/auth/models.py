"""JWT Payload Models"""
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime


class JWTPayload(BaseModel):
    """JWT token payload extracted from Keycloak"""
    auth_user_id: UUID = Field(..., alias="sub")  # Keycloak user ID
    internal_user_id: Optional[UUID] = None
    org_id: str
    tenant_schema: str
    roles: list[str] = []
    permissions: list[str] = []
    iat: Optional[datetime] = None
    exp: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
