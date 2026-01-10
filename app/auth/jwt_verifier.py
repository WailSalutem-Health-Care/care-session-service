"""JWT Token Verification"""
import requests
from jose import jwt, JWTError
from typing import Dict, Optional


class JWTVerifier:
    """Handles JWT token verification using Keycloak JWKS"""
    
    def __init__(self, keycloak_url: str, realm: str, algorithm: str = "RS256"):
        self.keycloak_url = keycloak_url
        self.realm = realm
        self.algorithm = algorithm
        self.jwks_url = f"{keycloak_url}/realms/{realm}/protocol/openid-connect/certs"
        self.issuer = f"{keycloak_url}/realms/{realm}"
        self._jwks_cache: Optional[Dict] = None
    
    def _get_jwks(self) -> Dict:
        """Fetch JWKS from Keycloak (cached)"""
        if self._jwks_cache is None:
            response = requests.get(self.jwks_url)
            response.raise_for_status()
            self._jwks_cache = response.json()
        return self._jwks_cache
    
    def verify_and_decode(self, token: str) -> Dict:
        """
        Verify JWT token signature and decode payload
        
        Raises:
            JWTError: Token is invalid or expired
        """
        jwks = self._get_jwks()
        
        payload = jwt.decode(
            token,
            jwks,
            algorithms=[self.algorithm],
            issuer=self.issuer,
            options={
                "verify_aud": False  # Keycloak doesn't always set audience
            },
        )
        
        return payload
