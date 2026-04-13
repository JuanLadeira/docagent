"""
Fase 21b — Criptografia de Secrets.

Testa encrypt/decrypt (Fernet), EncryptedString TypeDecorator e
comportamento de fallback quando ENCRYPTION_KEY não está configurada.
"""
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, mapped_column

from docagent.database import Base


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fernet_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture
def crypto_with_key(fernet_key, monkeypatch):
    """
    Configura docagent.crypto com uma chave Fernet ativa via monkeypatch.
    monkeypatch restaura automaticamente os atributos após o teste — sem
    importlib.reload e sem risco de vazar estado para testes seguintes.
    """
    from cryptography.fernet import Fernet as _Fernet
    import docagent.crypto as crypto_mod

    monkeypatch.setattr(crypto_mod, "_FERNET_KEY", fernet_key)
    monkeypatch.setattr(crypto_mod, "_fernet", _Fernet(fernet_key.encode()))
    return crypto_mod


# ── encrypt / decrypt ─────────────────────────────────────────────────────────

def test_encrypt_decrypt_roundtrip(crypto_with_key):
    plaintext = "sk-super-secreta-1234"
    ciphertext = crypto_with_key.encrypt(plaintext)
    assert ciphertext != plaintext
    assert crypto_with_key.decrypt(ciphertext) == plaintext


def test_encrypt_gera_valor_diferente_a_cada_chamada(crypto_with_key):
    """Fernet usa IV aleatório — dois encrypts do mesmo valor geram ciphertexts distintos."""
    v1 = crypto_with_key.encrypt("mesmo_valor")
    v2 = crypto_with_key.encrypt("mesmo_valor")
    assert v1 != v2


def test_decrypt_plaintext_legado_nao_falha(crypto_with_key):
    """Valores em plaintext (antes da migração) devem ser retornados sem erro."""
    resultado = crypto_with_key.decrypt("valor_plaintext_sem_prefixo_fernet")
    assert resultado == "valor_plaintext_sem_prefixo_fernet"


def test_is_encrypted_detecta_ciphertext(crypto_with_key):
    ciphertext = crypto_with_key.encrypt("qualquer")
    assert crypto_with_key.is_encrypted(ciphertext) is True
    assert crypto_with_key.is_encrypted("plaintext") is False


def test_sem_encryption_key_retorna_plaintext(monkeypatch):
    """Sem ENCRYPTION_KEY configurada, encrypt e decrypt são no-ops."""
    import docagent.crypto as crypto_mod

    monkeypatch.setattr(crypto_mod, "_FERNET_KEY", "")
    monkeypatch.setattr(crypto_mod, "_fernet", None)

    valor = "minha_chave_api"
    assert crypto_mod.encrypt(valor) == valor
    assert crypto_mod.decrypt(valor) == valor


# ── EncryptedString TypeDecorator no banco ────────────────────────────────────

class _ModeloTeste(Base):
    """Model temporário só para os testes de EncryptedString."""
    __tablename__ = "teste_encrypted_string"

    from docagent.crypto import EncryptedString
    secret: Mapped[str | None] = mapped_column(EncryptedString(700), nullable=True)


@pytest_asyncio.fixture
async def db_encrypted(fernet_key, monkeypatch):
    """Engine in-memory com chave Fernet ativa e tabela de teste."""
    from cryptography.fernet import Fernet as _Fernet
    import docagent.crypto as crypto_mod

    monkeypatch.setattr(crypto_mod, "_FERNET_KEY", fernet_key)
    monkeypatch.setattr(crypto_mod, "_fernet", _Fernet(fernet_key.encode()))

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield async_sessionmaker(engine, expire_on_commit=False), fernet_key

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_campo_salvo_criptografado_no_banco(db_encrypted):
    """O valor salvo na coluna raw do banco deve ser ciphertext, não plaintext."""
    from cryptography.fernet import Fernet as _Fernet
    from sqlalchemy import text

    session_factory, fernet_key = db_encrypted
    plaintext = "sk-minha-chave-secreta"

    async with session_factory() as session:
        obj = _ModeloTeste(secret=plaintext)
        session.add(obj)
        await session.commit()
        obj_id = obj.id

    # Lê o valor RAW (sem passar pelo TypeDecorator)
    async with session_factory() as session:
        result = await session.execute(
            text("SELECT secret FROM teste_encrypted_string WHERE id = :id"),
            {"id": obj_id},
        )
        raw_value = result.scalar_one()

    assert raw_value != plaintext, "O banco deve armazenar ciphertext, não plaintext"
    # Confirma que o raw_value é descriptografável com a chave correta
    fernet = _Fernet(fernet_key.encode())
    assert fernet.decrypt(raw_value.encode()).decode() == plaintext


@pytest.mark.asyncio
async def test_campo_retornado_descriptografado(db_encrypted):
    """Ao ler via ORM, o TypeDecorator deve retornar o plaintext."""
    session_factory, _ = db_encrypted
    plaintext = "minha-elevenlabs-key-xyz"

    async with session_factory() as session:
        obj = _ModeloTeste(secret=plaintext)
        session.add(obj)
        await session.commit()
        obj_id = obj.id

    async with session_factory() as session:
        result = await session.execute(
            select(_ModeloTeste).where(_ModeloTeste.id == obj_id)
        )
        obj = result.scalar_one()
        assert obj.secret == plaintext


@pytest.mark.asyncio
async def test_campo_none_persiste_como_none(db_encrypted):
    session_factory, _ = db_encrypted

    async with session_factory() as session:
        obj = _ModeloTeste(secret=None)
        session.add(obj)
        await session.commit()
        obj_id = obj.id

    async with session_factory() as session:
        result = await session.execute(
            select(_ModeloTeste).where(_ModeloTeste.id == obj_id)
        )
        obj = result.scalar_one()
        assert obj.secret is None
