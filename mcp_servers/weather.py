"""
MCP Server de Clima — Open-Meteo (gratuito, sem chave de API)

Ferramentas expostas:
  - get_forecast(city, days): previsão do tempo em tempo real para qualquer cidade

Transport: stdio (padrão MCP)
"""
import json
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("weather")

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WMO_CODES = {
    0: "Céu limpo",
    1: "Predominantemente limpo",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Neblina",
    48: "Neblina com geada",
    51: "Garoa leve",
    53: "Garoa moderada",
    55: "Garoa densa",
    61: "Chuva fraca",
    63: "Chuva moderada",
    65: "Chuva forte",
    71: "Neve fraca",
    73: "Neve moderada",
    75: "Neve forte",
    80: "Pancadas de chuva fracas",
    81: "Pancadas de chuva moderadas",
    82: "Pancadas de chuva violentas",
    95: "Trovoada",
    96: "Trovoada com granizo",
    99: "Trovoada com granizo forte",
}


def _geocode(city: str) -> dict | None:
    """Converte nome de cidade em lat/lon via Open-Meteo Geocoding API."""
    resp = httpx.get(
        GEOCODING_URL,
        params={"name": city, "count": 1, "language": "pt", "format": "json"},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("results")
    if not results:
        return None
    r = results[0]
    return {
        "name": r.get("name", city),
        "country": r.get("country", ""),
        "latitude": r["latitude"],
        "longitude": r["longitude"],
    }


def _fetch_forecast(lat: float, lon: float, days: int) -> dict:
    """Busca previsão do tempo via Open-Meteo Forecast API."""
    resp = httpx.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "weathercode",
                "windspeed_10m_max",
            ],
            "current_weather": True,
            "timezone": "America/Sao_Paulo",
            "forecast_days": min(days, 7),
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_forecast(city: str, days: int = 3) -> str:
    """
    Retorna a previsão do tempo em tempo real para uma cidade.

    Args:
        city: Nome da cidade (ex: "Nova Iguaçu", "São Paulo", "Rio de Janeiro")
        days: Número de dias de previsão (1 a 7, padrão 3)
    """
    days = max(1, min(days, 7))

    location = _geocode(city)
    if not location:
        return f"Cidade '{city}' não encontrada. Tente com o nome completo ou adicione o estado/país."

    data = _fetch_forecast(location["latitude"], location["longitude"], days)

    current = data.get("current_weather", {})
    daily = data.get("daily", {})

    lines = [
        f"📍 {location['name']}, {location['country']}",
        f"🌡️  Agora: {current.get('temperature', '?')}°C — "
        f"{WMO_CODES.get(current.get('weathercode', -1), 'Condição desconhecida')}",
        f"💨 Vento atual: {current.get('windspeed', '?')} km/h",
        "",
        f"📅 Previsão para {days} dia(s):",
    ]

    dates = daily.get("time", [])
    for i, date in enumerate(dates):
        code = daily.get("weathercode", [])[i] if i < len(daily.get("weathercode", [])) else -1
        tmax = daily.get("temperature_2m_max", [])[i] if i < len(daily.get("temperature_2m_max", [])) else "?"
        tmin = daily.get("temperature_2m_min", [])[i] if i < len(daily.get("temperature_2m_min", [])) else "?"
        rain = daily.get("precipitation_sum", [])[i] if i < len(daily.get("precipitation_sum", [])) else "?"
        wind = daily.get("windspeed_10m_max", [])[i] if i < len(daily.get("windspeed_10m_max", [])) else "?"
        cond = WMO_CODES.get(code, "Condição desconhecida")

        lines.append(
            f"  {date}: {tmin}°C–{tmax}°C | {cond} | "
            f"Chuva: {rain}mm | Vento máx: {wind} km/h"
        )

    source_url = (
        f"https://open-meteo.com/en/docs"
        f"?latitude={location['latitude']}&longitude={location['longitude']}"
    )
    lines += [
        "",
        f"🔗 Fonte: Open-Meteo ({source_url})",
        "ℹ️  Dados em tempo real, atualizados a cada hora.",
    ]

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")
