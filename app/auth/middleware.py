from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer
from datetime import datetime
import jwt
from jwt import PyJWKClient
from app.config import settings
import yaml
from pathlib import Path


security = HTTPBearer()


class JWTPayload(BaseModel):
    """JWT token payload"""
    user_id: UUID = Field(..., alias="sub")
    org_id: str  # organizationId from Keycloak
    tenant_schema: str
    roles: list[str] = []
    permissions: list[str] = []
    iat: Optional[datetime] = None
    exp: Optional[datetime] = None
    
    class Config:
        populate_by_name = True


# Load permissions from permissions.yml
def load_permissions():
    """Load role-to-permissions mapping from permissions.yml"""
    permissions_file = Path(__file__).parent.parent.parent / "permissions.yml"
    try:
        with open(permissions_file, 'r') as f:
            data = yaml.safe_load(f)
            return data.get('roles', {})
    except Exception:
        return {}


ROLE_PERMISSIONS = load_permissions()


def get_permissions_from_roles(roles: list[str]) -> list[str]:
    """Convert roles to permissions using permissions.yml"""
    permissions = set()
    for role in roles:
        role_perms = ROLE_PERMISSIONS.get(role, [])
        permissions.update(role_perms)
    return list(permissions)


async def verify_token(credentials = Depends(security)) -> JWTPayload:
    """
    Verify JWT token from Keycloak using JWKS.
    
    Expected JWT claims from Keycloak:
    - sub: user_id
    - organisationId: organization ID
    - realm_access.roles: list of role names
    """
    token = credentials.credentials
    
    try:
        # Use Keycloak's JWKS endpoint for token verification
        jwks_url = "https://keycloak-wailsalutem-suite.apps.inholland-minor.openshift.eu/realms/wailsalutem/protocol/openid-connect/certs"
        jwks_client = PyJWKClient(jwks_url)
        
        # Get signing key from token
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        # Verify and decode token
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience="account",
            options={"verify_exp": True}
        )
        
        # Extract roles from realm_access
        roles = []
        if "realm_access" in payload and "roles" in payload["realm_access"]:
            roles = payload["realm_access"]["roles"]
        
        # Get organizationId (Keycloak uses this field)
        org_id = payload.get("organisationId", "")
        if not org_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing organisationId"
            )
        
        # Map roles to permissions using permissions.yml
        permissions = get_permissions_from_roles(roles)
        
        # Build tenant schema from org_id (format: org_<id>)
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
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token verification failed: {str(e)}"
        )
