from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class AdminCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    nome: str


class AdminPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    nome: str
    ativo: bool
    totp_habilitado: bool
    created_at: datetime
    updated_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str


# ── 2FA schemas ───────────────────────────────────────────────────────────────

class LoginResponse(BaseModel):
    """
    Resposta do POST /api/admin/login.
    Se requires_2fa=True, o cliente deve fazer POST /api/admin/login/2fa
    com o temp_token e o código TOTP.
    Se requires_2fa=False, access_token é o JWT definitivo.
    """
    access_token: str | None = None
    token_type: str = "bearer"
    requires_2fa: bool = False
    temp_token: str | None = None


class TotpVerifyRequest(BaseModel):
    temp_token: str
    codigo: str


class TotpSetupResponse(BaseModel):
    """Resposta do GET /api/admin/2fa/setup — URI para gerar QR code."""
    qr_uri: str
    secret: str  # exibir só durante o setup; o frontend não deve persistir


class TotpConfirmRequest(BaseModel):
    codigo: str  # admin confirma que escaneou e o app está gerando códigos corretos


class TotpStatusResponse(BaseModel):
    totp_habilitado: bool
