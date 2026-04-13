"""
TOTP — 2FA para admin (Fase 21d).

Usa pyotp (RFC 6238) — compatível com Google Authenticator, Authy, etc.
O secret é armazenado criptografado (EncryptedString) no model Admin.
"""
import pyotp


def gerar_secret() -> str:
    """Gera um novo secret TOTP aleatório (base32, 32 chars)."""
    return pyotp.random_base32()


def gerar_qr_uri(secret: str, username: str, issuer: str = "z3ndocs Admin") -> str:
    """
    Retorna a URI otpauth:// para gerar QR code no frontend.
    O frontend usa uma lib como qrcode.js para renderizar.
    """
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name=issuer)


def verificar_codigo(secret: str, codigo: str) -> bool:
    """
    Valida um código TOTP de 6 dígitos.
    valid_window=1 aceita ±30s de tolerância (1 janela anterior/posterior).
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(codigo, valid_window=1)
