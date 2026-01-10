"""Authentication Middleware"""
import os
from jose import JWTError
from fastapi import HTTPException, status, Depends, Header
from fastapi.security import HTTPBearer
from typing import Optional
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import JWTPayload
from app.auth.jwt_verifier import JWTVerifier
from app.auth.permissions_manager import PermissionsManager
from app.db.postgres import get_db
from app.db.models import Organization


# Initialize components
security = HTTPBearer()
jwt_verifier = JWTVerifier(
    keycloak_url=os.getenv("KEYCLOAK_BASE_URL"),
    realm=os.getenv("KEYCLOAK_REALM"),
    algorithm=os.getenv("JWT_ALGORITHM")
)
permissions_manager = PermissionsManager()


async def verify_token(
    credentials = Depends(security),
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-ID"),
    db: AsyncSession = Depends(get_db)
) -> JWTPayload:
    """
    Verify JWT token from Keycloak and extract payload.
    
    Expected JWT claims:
    - sub: user_id
    - organizationID: organizationID (or X-Organization-ID header for SUPER_ADMIN)
    - realm_access.roles: list of role names
    """
    token = credentials.credentials
    
    try:
        # Verify and decode token
        payload = jwt_verifier.verify_and_decode(token)
        
        # Extract roles from realm_access
        roles = []
        if "realm_access" in payload and "roles" in payload["realm_access"]:
            roles = payload["realm_access"]["roles"]
        
        # Check if user is SUPER_ADMIN
        is_super_admin = "SUPER_ADMIN" in roles
        
        # Get organizationId from token or header
        # SUPER_ADMIN can provide org via X-Organization-ID header
        org_id = payload.get("organizationID", "")
        if not org_id and x_organization_id and is_super_admin:
            org_id = x_organization_id
        elif not org_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing organizationID"
            )
        
        # Map roles to permissions
        permissions = permissions_manager.get_permissions_for_roles(roles)
        
        # Get tenant schema from token
        tenant_schema = payload.get("orgSchemaName") or payload.get("schemaName") or payload.get("schema_name")
        
        if not tenant_schema:
            # For SUPER_ADMIN with X-Organization-ID header, query the schema name from database
            if is_super_admin and x_organization_id:
                stmt = select(Organization.schema_name).where(Organization.id == org_id)
                result = await db.execute(stmt)
                tenant_schema = result.scalar_one_or_none()
                
                if not tenant_schema:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Organization not found: {org_id}"
                    )
            else:
                # Fallback: construct from org_id (for backward compatibility)
                tenant_schema = org_id if org_id.startswith("org_") else f"org_{org_id}"
        
        return JWTPayload(
            sub=payload["sub"],
            org_id=org_id,
            tenant_schema=tenant_schema,
            roles=roles,
            permissions=permissions,
            iat=payload.get("iat"),
            exp=payload.get("exp")
        )
    
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token verification failed: {str(e)}"
        )


def check_permission(jwt_payload: JWTPayload, required_permission: str):
    """
    Check if user has required permission.
    
    Args:
        jwt_payload: JWT payload containing user permissions
        required_permission: Permission string to check
        
    Raises:
        HTTPException: If user lacks required permission
    """
    if required_permission not in jwt_payload.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required permission: {required_permission}"
        )
