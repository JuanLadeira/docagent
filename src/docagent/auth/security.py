from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi.security import OAuth2PasswordBearer
from jwt import encode
from pwdlib import PasswordHash

from docagent.settings import Settings

settings = Settings()
pwd_context = PasswordHash.recommended()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", refreshUrl="auth/refresh")

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(tz=ZoneInfo("UTC")) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    encoded_jwt = encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_password_reset_token(email: str) -> str:
    expire = datetime.now(tz=ZoneInfo("UTC")) + timedelta(hours=1)
    data = {"sub": email, "type": "password_reset", "exp": expire}
    return encode(data, SECRET_KEY, algorithm=ALGORITHM)


def create_temp_token(admin_id: int) -> str:
    """Token temporário para o segundo passo do login 2FA. Expira em 5 minutos."""
    expire = datetime.now(tz=ZoneInfo("UTC")) + timedelta(minutes=5)
    data = {"sub": f"temp_2fa:{admin_id}", "type": "temp_2fa", "exp": expire}
    return encode(data, SECRET_KEY, algorithm=ALGORITHM)


def verify_temp_token(token: str) -> int | None:
    """Valida o temp_token e retorna o admin_id, ou None se inválido/expirado."""
    from jwt import DecodeError, ExpiredSignatureError, decode
    try:
        payload = decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "temp_2fa":
            return None
        sub = payload.get("sub", "")
        if not sub.startswith("temp_2fa:"):
            return None
        return int(sub.split(":")[1])
    except (DecodeError, ExpiredSignatureError, ValueError):
        return None


def verify_password_reset_token(token: str) -> str | None:
    from jwt import DecodeError, ExpiredSignatureError, decode
    try:
        payload = decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "password_reset":
            return None
        return payload.get("sub")
    except (DecodeError, ExpiredSignatureError):
        return None


def get_password_hash(password: str):
    """Hash the provided password using the recommended hashing algorithm."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify if the provided plain password matches the hashed password."""
    return pwd_context.verify(plain_password, hashed_password)
