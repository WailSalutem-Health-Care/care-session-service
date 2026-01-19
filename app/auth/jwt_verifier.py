"""JWT Token Verification with retry logic"""

import logging
from typing import Dict, Optional

import requests
from jose import jwt
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class JWTVerifier:
    """Handles JWT token verification using Keycloak JWKS"""

    def __init__(self, keycloak_url: str, realm: str, algorithm: str = "RS256"):
        self.keycloak_url = keycloak_url
        self.realm = realm
        self.algorithm = algorithm
        self.jwks_url = f"{keycloak_url}/realms/{realm}/protocol/openid-connect/certs"
        self.issuer = f"{keycloak_url}/realms/{realm}"
        self._jwks_cache: Optional[Dict] = None

    @retry(
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _get_jwks(self) -> Dict:
        """Fetch JWKS from Keycloak with retry logic"""
        if self._jwks_cache is None:
            response = requests.get(self.jwks_url, timeout=5)
            response.raise_for_status()
            self._jwks_cache = response.json()
        return self._jwks_cache

    def verify_and_decode(self, token: str) -> Dict:
        """Verify JWT token signature and decode payload"""
        jwks = self._get_jwks()
        payload = jwt.decode(
            token,
            jwks,
            algorithms=[self.algorithm],
            issuer=self.issuer,
            options={"verify_aud": False},
        )
        return payload
