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


async def get_crypto_news() -> list:
    """Fetch real crypto news headlines from CryptoCompare (free, no API key needed)."""
    url = "https://min-api.cryptocompare.com/data/v2/news/"
    params = {"lang": "EN", "sortOrder": "latest"}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        articles = []
        now = datetime.utcnow().timestamp()
        for item in data.get("Data", [])[:10]:
            published_ts = item.get("published_on", 0)
            age_seconds = now - published_ts if published_ts else 0
            if age_seconds < 3600:
                time_label = f"{int(age_seconds // 60)}m ago"
            elif age_seconds < 86400:
                time_label = f"{int(age_seconds // 3600)}h ago"
            else:
                time_label = f"{int(age_seconds // 86400)}d ago"

            body = item.get("body", "")
            articles.append({
                "title": item.get("title", ""),
                "source": item.get("source_info", {}).get("name", item.get("source", "")),
                "published_at": time_label,
                "url": item.get("url", ""),
                "body_snippet": body[:120].strip() + ("..." if len(body) > 120 else ""),
                "categories": item.get("categories", "")
            })
        return articles
    except Exception as e:
        return []


async def get_price_history(coin_id: str = "bitcoin", days: int = 30) -> list:
    """Fetch price history for charting and technical indicators"""
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


# ---------------------------------------------------------------------------
# Technical indicator calculations
# ---------------------------------------------------------------------------

def _calculate_rsi(prices: list, period: int = 14) -> float:
    """Calculate RSI (Relative Strength Index) from a list of prices."""
    if len(prices) < period + 1:
        return 50.0

    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [c if c > 0 else 0.0 for c in changes]
    losses = [-c if c < 0 else 0.0 for c in changes]

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def _calculate_ema(prices: list, period: int) -> list:
    """Calculate Exponential Moving Average."""
    if len(prices) < period:
        return prices[:]

    multiplier = 2 / (period + 1)
    ema = [sum(prices[:period]) / period]
    for price in prices[period:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])
    return ema


def _calculate_macd(prices: list) -> dict:
    """Calculate MACD (12, 26, 9)."""
    if len(prices) < 35:
        return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}

    ema12 = _calculate_ema(prices, 12)
    ema26 = _calculate_ema(prices, 26)

    # ema12 has 14 more values than ema26; align from the ema26 start
    offset = len(ema12) - len(ema26)
    macd_line = [ema12[i + offset] - ema26[i] for i in range(len(ema26))]

    if len(macd_line) < 9:
        return {"macd": round(macd_line[-1], 4), "signal": 0.0, "histogram": round(macd_line[-1], 4)}

    signal_line = _calculate_ema(macd_line, 9)
    macd_val = macd_line[-1]
    signal_val = signal_line[-1]

    return {
        "macd": round(macd_val, 4),
        "signal": round(signal_val, 4),
        "histogram": round(macd_val - signal_val, 4)
    }


def _calculate_bollinger_bands(prices: list, period: int = 20, num_std: float = 2.0) -> dict:
    """Calculate Bollinger Bands."""
    current = prices[-1] if prices else 0.0
    if len(prices) < period:
        return {"upper": current, "middle": current, "lower": current, "width_percent": 0.0}

    recent = prices[-period:]
    sma = sum(recent) / period
    variance = sum((p - sma) ** 2 for p in recent) / period
    std_dev = variance ** 0.5

    upper = sma + num_std * std_dev
    lower = sma - num_std * std_dev
    width_percent = ((upper - lower) / sma) * 100 if sma else 0.0

    return {
        "upper": round(upper, 2),
        "middle": round(sma, 2),
        "lower": round(lower, 2),
        "width_percent": round(width_percent, 2)
    }


async def get_technical_indicators(coin_id: str, symbol: str) -> dict:
    """Calculate technical indicators from 90-day price history."""
    try:
        history = await get_price_history(coin_id, days=90)
        prices = [p["price"] for p in history]
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

    if len(prices) < 15:
        return {"symbol": symbol, "error": "Insufficient price history"}

    rsi = _calculate_rsi(prices, period=14)
    macd = _calculate_macd(prices)
    bb = _calculate_bollinger_bands(prices, period=20)

    ema9 = _calculate_ema(prices, 9)
    ema21 = _calculate_ema(prices, 21)

    # Align EMA lists (ema21 is shorter)
    ema9_last = ema9[-1] if ema9 else None
    ema21_last = ema21[-1] if ema21 else None

    ema_crossover = "neutral"
    if ema9_last is not None and ema21_last is not None:
        ema_crossover = "bullish" if ema9_last > ema21_last else "bearish"

    current_price = prices[-1]

    # Bollinger Band position signal
    if current_price > bb["upper"]:
        bb_signal = "overbought (above upper band)"
    elif current_price < bb["lower"]:
        bb_signal = "oversold (below lower band)"
    else:
        band_range = bb["upper"] - bb["lower"]
        pos_pct = ((current_price - bb["lower"]) / band_range * 100) if band_range else 50.0
        bb_signal = f"in_band ({pos_pct:.0f}% from lower)"

    # RSI signal
    if rsi >= 70:
        rsi_signal = "overbought"
    elif rsi <= 30:
        rsi_signal = "oversold"
    else:
        rsi_signal = "neutral"

    # MACD signal
    macd_signal = "bullish" if macd["histogram"] > 0 else "bearish"
    macd_cross = "no_cross"
    if len(prices) >= 2:
        # Check for recent crossover using last two MACD histogram values
        ema12 = _calculate_ema(prices, 12)
        ema26 = _calculate_ema(prices, 26)
        if len(ema12) >= 2 and len(ema26) >= 2:
            offset = len(ema12) - len(ema26)
            if offset >= 0 and len(ema12) > offset + 1:
                prev_macd = ema12[-(2 + offset) + offset] - ema26[-2] if len(ema26) >= 2 else macd["macd"]
                curr_macd = macd["macd"]
                if prev_macd <= 0 and curr_macd > 0:
                    macd_cross = "bullish_crossover"
                elif prev_macd >= 0 and curr_macd < 0:
                    macd_cross = "bearish_crossover"

    # Volume trend (last 7 days vs prior 7 days)
    volume_trend = "stable"
    if len(history) >= 14:
        recent_prices = [h["price"] for h in history[-7:]]
        prior_prices = [h["price"] for h in history[-14:-7]]
        # Use price momentum as a volume proxy since we only have prices
        recent_change = (recent_prices[-1] - recent_prices[0]) / recent_prices[0] * 100
        prior_change = (prior_prices[-1] - prior_prices[0]) / prior_prices[0] * 100
        if abs(recent_change) > abs(prior_change) * 1.5:
            volume_trend = "accelerating"
        elif abs(recent_change) < abs(prior_change) * 0.5:
            volume_trend = "decelerating"

    return {
        "symbol": symbol,
        "rsi": rsi,
        "rsi_signal": rsi_signal,
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_crossover": macd_cross,
        "bollinger_bands": bb,
        "bb_signal": bb_signal,
        "ema9": round(ema9_last, 2) if ema9_last is not None else None,
        "ema21": round(ema21_last, 2) if ema21_last is not None else None,
        "ema_crossover": ema_crossover,
        "momentum_trend": volume_trend
    }


async def get_fear_greed_index() -> dict:
    """Fetch the Crypto Fear & Greed Index from alternative.me."""
    url = "https://api.alternative.me/fng/"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, params={"limit": 1})
            response.raise_for_status()
            data = response.json()

        entry = data.get("data", [{}])[0]
        return {
            "value": int(entry.get("value", 50)),
            "label": entry.get("value_classification", "Neutral"),
            "timestamp": entry.get("timestamp", "")
        }
    except Exception as e:
        return {"value": 50, "label": "Neutral", "error": str(e)}


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

    try:
        news = await get_crypto_news()
    except Exception as e:
        news = []

    # Fetch technical indicators for each tracked coin
    coin_id_map = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}
    technical_indicators = {}
    for symbol, coin_id in coin_id_map.items():
        try:
            technical_indicators[symbol] = await get_technical_indicators(coin_id, symbol)
        except Exception as e:
            technical_indicators[symbol] = {"symbol": symbol, "error": str(e)}

    # Fetch Fear & Greed Index
    try:
        fear_greed = await get_fear_greed_index()
    except Exception as e:
        fear_greed = {"value": 50, "label": "Neutral", "error": str(e)}

    return {
        "timestamp": timestamp,
        "prices": prices,
        "market": market,
        "trending": trending,
        "news": news,
        "technical_indicators": technical_indicators,
        "fear_greed_index": fear_greed
    }
