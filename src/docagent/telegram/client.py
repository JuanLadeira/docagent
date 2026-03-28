import httpx


def get_telegram_client(bot_token: str) -> httpx.AsyncClient:
    """Retorna um AsyncClient configurado para a Telegram Bot API do bot informado."""
    return httpx.AsyncClient(
        base_url=f"https://api.telegram.org/bot{bot_token}",
        timeout=30.0,
    )
