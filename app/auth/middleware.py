"""Authentication Middleware"""
import os
from jose import JWTError
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer

from app.auth.models import JWTPayload
from app.auth.jwt_verifier import JWTVerifier
from app.auth.permissions_manager import PermissionsManager


# Initialize components
security = HTTPBearer()
jwt_verifier = JWTVerifier(
    keycloak_url=os.getenv("KEYCLOAK_URL"),
    realm=os.getenv("KEYCLOAK_REALM"),
    algorithm=os.getenv("JWT_ALGORITHM")
)
permissions_manager = PermissionsManager()


async def verify_token(credentials = Depends(security)) -> JWTPayload:
    """
    Verify JWT token from Keycloak and extract payload.
    
    Expected JWT claims:
    - sub: user_id
    - organisationId: organization ID
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
        
        # Get organizationId
        org_id = payload.get("organisationId", "")
        if not org_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing organisationId"
            )
        
        # Map roles to permissions
        permissions = permissions_manager.get_permissions_for_roles(roles)
        
        # Build tenant schema
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
