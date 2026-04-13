"""
Criptografia de campos sensíveis — Fase 21b.

Usa Fernet (AES-128-CBC + HMAC-SHA256) para criptografar secrets no banco.

Configuração:
    ENCRYPTION_KEY=<base64url 32 bytes>
    Gerar: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Se ENCRYPTION_KEY não estiver configurada, os valores são salvos em plaintext
com um aviso de log — facilita o desenvolvimento local sem configuração extra.
Em produção a chave é obrigatória.

ATENÇÃO: a ENCRYPTION_KEY é crítica. Perder a chave = perder todos os secrets
criptografados. Fazer backup seguro. Rotação de chave requer re-criptografar
todos os registros (ver script em alembic/scripts/reencrypt_secrets.py).
"""
import logging
import os

from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

_log = logging.getLogger(__name__)

_FERNET_KEY = os.getenv("ENCRYPTION_KEY", "")
_fernet = None

if _FERNET_KEY:
    from cryptography.fernet import Fernet
    _fernet = Fernet(_FERNET_KEY.encode())
else:
    _log.warning(
        "ENCRYPTION_KEY não configurada — secrets serão salvos em plaintext. "
        "Configure a variável de ambiente em produção."
    )


def encrypt(plaintext: str) -> str:
    """Criptografa um valor. Retorna plaintext se ENCRYPTION_KEY não configurada."""
    if _fernet is None:
        return plaintext
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """
    Descriptografa um valor.
    Se o valor não parece criptografado (plaintext legado ou ENCRYPTION_KEY ausente),
    retorna o valor original sem erro — permite migração gradual.
    """
    if _fernet is None:
        return ciphertext
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except Exception:
        # Valor em plaintext (antes da migração) — retorna sem falhar
        return ciphertext


def is_encrypted(value: str) -> bool:
    """Verifica se um valor já está criptografado (prefixo Fernet = 'gAAAAA')."""
    return value.startswith("gAAAAA")


class EncryptedString(TypeDecorator):
    """
    TypeDecorator SQLAlchemy que criptografa ao gravar e descriptografa ao ler.

    Uso nos models:
        from docagent.crypto import EncryptedString

        class MyModel(Base):
            secret: Mapped[str | None] = mapped_column(EncryptedString(500), nullable=True)

    O tamanho (500) se refere ao tamanho da string criptografada no banco,
    que é maior que o plaintext (~1.37× + overhead base64).
    """
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Chamado ao gravar no banco — criptografa."""
        if value is not None:
            return encrypt(value)
        return value

    def process_result_value(self, value, dialect):
        """Chamado ao ler do banco — descriptografa."""
        if value is not None:
            return decrypt(value)
        return value
