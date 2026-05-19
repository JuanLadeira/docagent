from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient


class KeycloakClient:
    def __init__(self, url: str, realm: str, client_id: str, client_secret: str):
        self.url = url.rstrip("/")
        self.realm = realm
        self.client_id = client_id
        self.client_secret = client_secret
        self._token_url = f"{self.url}/realms/{realm}/protocol/openid-connect/token"
        self._auth_url = f"{self.url}/realms/{realm}/protocol/openid-connect/auth"
        self._jwks_uri = f"{self.url}/realms/{realm}/protocol/openid-connect/certs"
        # PyJWKClient faz cache das chaves por `lifespan` segundos
        self._jwks_client = PyJWKClient(self._jwks_uri, cache_keys=True, lifespan=600)

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "scope": "openid email profile",
            "redirect_uri": redirect_uri,
            "state": state,
        }
        return f"{self._auth_url}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self._token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def refresh(self, refresh_token: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self._token_url,
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                },
            )
            resp.raise_for_status()
            return resp.json()

    def validate_jwt(self, token: str) -> dict:
        signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
