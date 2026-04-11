from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from docagent.auth.schemas import ChangePasswordRequest, ForgotPasswordRequest, ResetPasswordRequest
from docagent.auth.security import (
    create_access_token,
    create_password_reset_token,
    get_password_hash,
    verify_password,
    verify_password_reset_token,
)
from docagent.auth.current_user import CurrentUser
from docagent.rate_limit import limiter
from docagent.settings import Settings
from docagent.usuario.services import UsuarioServiceDep

settings = Settings()

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
    responses={404: {"description": "Not found"}},
)


@router.post("/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    service: UsuarioServiceDep,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    user = await service.get_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
@limiter.limit("3/hour")
async def forgot_password(request: Request, data: ForgotPasswordRequest, service: UsuarioServiceDep):
    user = await service.get_by_email(data.email)
    if not user:
        # Retorna 200 mesmo se o email não existir (evita enumeração de usuários)
        return {"message": "Se o email existir, você receberá um link de recuperação."}

    token = create_password_reset_token(user.email)
    # TODO: integrar servico de email (Fase futura)
    # Por ora, o token e retornado no response para facilitar testes/desenvolvimento.
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    print(f"[DEV] Reset link para {user.email}: {reset_link}")

    return {"message": "Se o email existir, você receberá um link de recuperação."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
@limiter.limit("3/hour")
async def reset_password(request: Request, data: ResetPasswordRequest, service: UsuarioServiceDep):
    email = verify_password_reset_token(data.token)
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido ou expirado")

    user = await service.get_by_email(email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    user.password = get_password_hash(data.new_password)
    await service.session.flush()
    await service.session.refresh(user)

    return {"message": "Senha redefinida com sucesso"}


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    data: ChangePasswordRequest,
    current_user: CurrentUser,
    service: UsuarioServiceDep,
):
    if not verify_password(data.current_password, current_user.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha atual incorreta")

    current_user.password = get_password_hash(data.new_password)
    await service.session.flush()

    return {"message": "Senha alterada com sucesso"}
