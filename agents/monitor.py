"""
Monitor Agent - Fetches crypto prices, news, and market data
"""
import httpx
from datetime import datetime
from typing import Optional


COINS = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL"
}


async def get_prices() -> dict:
    """Fetch current prices from CoinGecko (free, no API key needed)"""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin,ethereum,solana",
        "vs_currencies": "usd",
        "include_24hr_change": "true",
        "include_24hr_vol": "true",
        "include_market_cap": "true"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    result = {}
    for coin_id, symbol in COINS.items():
        if coin_id in data:
            result[symbol] = {
                "price": data[coin_id].get("usd", 0),
                "change_24h": data[coin_id].get("usd_24h_change", 0),
                "volume_24h": data[coin_id].get("usd_24h_vol", 0),
                "market_cap": data[coin_id].get("usd_market_cap", 0)
            }

    return result


async def get_market_data() -> dict:
    """Fetch detailed market data including fear/greed approximation"""
    url = "https://api.coingecko.com/api/v3/global"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()["data"]

    return {
        "total_market_cap": data.get("total_market_cap", {}).get("usd", 0),
        "total_volume": data.get("total_volume", {}).get("usd", 0),
        "btc_dominance": data.get("market_cap_percentage", {}).get("btc", 0),
        "eth_dominance": data.get("market_cap_percentage", {}).get("eth", 0),
        "market_cap_change_24h": data.get("market_cap_change_percentage_24h_usd", 0)
    }


async def get_news() -> list:
    """Fetch crypto news from CoinGecko status updates (free)"""
    # Using CoinGecko's trending endpoint as a proxy for market interest
    url = "https://api.coingecko.com/api/v3/search/trending"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    trending = []
    for item in data.get("coins", [])[:5]:
        coin = item.get("item", {})
        trending.append({
            "name": coin.get("name", ""),
            "symbol": coin.get("symbol", ""),
            "market_cap_rank": coin.get("market_cap_rank", 0),
            "score": coin.get("score", 0)
        })

    return trending


async def get_price_history(coin_id: str = "bitcoin", days: int = 7) -> list:
    """Fetch price history for charting"""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": "usd",
        "days": days
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    prices = []
    for item in data.get("prices", []):
        prices.append({
            "timestamp": item[0],
            "price": item[1]
        })

    return prices


async def run_monitor() -> dict:
    """Run the full monitor agent and return all data"""
    timestamp = datetime.utcnow().isoformat()

    try:
        prices = await get_prices()
    except Exception as e:
        prices = {"error": str(e)}

    try:
        market = await get_market_data()
    except Exception as e:
        market = {"error": str(e)}

    try:
        trending = await get_news()
    except Exception as e:
        trending = {"error": str(e)}

    return {
        "timestamp": timestamp,
        "prices": prices,
        "market": market,
        "trending": trending
    }
