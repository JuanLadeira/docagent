from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jwt import DecodeError, ExpiredSignatureError, decode

from docagent.admin.models import Admin
from docagent.admin.services import AdminServiceDep
from docagent.settings import Settings

settings = Settings()

admin_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/admin/login")

_SECRET_KEY = settings.SECRET_KEY
_ALGORITHM = settings.ALGORITHM

# Token prefix to ensure user tokens cannot be used in admin endpoints
ADMIN_PREFIX = "admin:"


async def get_current_admin(
    service: AdminServiceDep,
    token: str = Depends(admin_oauth2_scheme),
) -> Admin:
    credentials_exception = HTTPException(
        status_code=HTTPStatus.UNAUTHORIZED,
        detail="Could not validate admin credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        sub: str | None = payload.get("sub")

        if not sub or not sub.startswith(ADMIN_PREFIX):
            raise credentials_exception

        username = sub[len(ADMIN_PREFIX):]

    except (DecodeError, ExpiredSignatureError):
        raise credentials_exception

    admin = await service.get_by_username(username)
    if not admin or not admin.ativo:
        raise credentials_exception

    return admin


CurrentAdmin = Annotated[Admin, Depends(get_current_admin)]
