"""
Analysis Agent - Analyzes market data and identifies trends using Claude
"""
import os
import json
from anthropic import Anthropic
from typing import Optional


def get_client() -> Anthropic:
    """Get Anthropic client"""
    return Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


async def analyze_market(monitor_data: dict) -> dict:
    """Use Claude to analyze the market data and identify trends"""
    client = get_client()

    prices = monitor_data.get("prices", {})
    market = monitor_data.get("market", {})
    trending = monitor_data.get("trending", [])
    tech_indicators = monitor_data.get("technical_indicators", {})
    fear_greed = monitor_data.get("fear_greed_index", {})
    news = monitor_data.get("news", [])

    prompt = f"""You are a crypto market analyst. Analyze the following market data and provide insights.

CURRENT PRICES:
{_format_prices(prices)}

MARKET OVERVIEW:
- Total Market Cap: ${market.get('total_market_cap', 0):,.0f}
- 24h Volume: ${market.get('total_volume', 0):,.0f}
- BTC Dominance: {market.get('btc_dominance', 0):.1f}%
- ETH Dominance: {market.get('eth_dominance', 0):.1f}%
- Market Cap Change 24h: {market.get('market_cap_change_24h', 0):.2f}%

FEAR & GREED INDEX:
{fear_greed.get('value', 50)}/100 — {fear_greed.get('label', 'Neutral')}
(0-25=Extreme Fear, 26-45=Fear, 46-55=Neutral, 56-75=Greed, 76-100=Extreme Greed)

TECHNICAL INDICATORS (90-day history):
{_format_technical_indicators(tech_indicators)}

TRENDING COINS:
{_format_trending(trending)}

RECENT INDUSTRY NEWS:
{_format_news_for_prompt(news)}

Provide analysis in the following JSON format:
{{
    "market_sentiment": "bullish" | "bearish" | "neutral",
    "sentiment_score": <number from -100 to 100>,
    "fear_greed_interpretation": "<one sentence on what the fear/greed reading implies>",
    "news_sentiment": "positive" | "negative" | "neutral",
    "key_news_drivers": ["<headline theme 1>", "<headline theme 2>"],
    "btc_analysis": {{
        "trend": "up" | "down" | "sideways",
        "strength": "strong" | "moderate" | "weak",
        "technical_bias": "bullish" | "bearish" | "neutral",
        "key_factors": ["factor1", "factor2", "factor3"]
    }},
    "eth_analysis": {{
        "trend": "up" | "down" | "sideways",
        "strength": "strong" | "moderate" | "weak",
        "technical_bias": "bullish" | "bearish" | "neutral",
        "key_factors": ["factor1", "factor2", "factor3"]
    }},
    "sol_analysis": {{
        "trend": "up" | "down" | "sideways",
        "strength": "strong" | "moderate" | "weak",
        "technical_bias": "bullish" | "bearish" | "neutral",
        "key_factors": ["factor1", "factor2", "factor3"]
    }},
    "market_summary": "<3-4 sentence summary incorporating technicals, sentiment, and news>",
    "risk_level": "low" | "medium" | "high"
}}

Respond ONLY with the JSON, no other text."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = response.content[0].text.strip()

    try:
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        analysis = json.loads(response_text)
    except json.JSONDecodeError:
        analysis = {
            "market_sentiment": "neutral",
            "sentiment_score": 0,
            "market_summary": response_text[:500],
            "risk_level": "medium",
            "error": "Could not parse structured response"
        }

    return analysis


def _format_prices(prices: dict) -> str:
    """Format prices for the prompt"""
    lines = []
    for symbol, data in prices.items():
        if isinstance(data, dict):
            lines.append(f"- {symbol}: ${data.get('price', 0):,.2f} ({data.get('change_24h', 0):+.2f}% 24h)")
    return "\n".join(lines) if lines else "No price data available"


def _format_trending(trending: list) -> str:
    """Format trending coins for the prompt"""
    if not trending or isinstance(trending, dict):
        return "No trending data available"
    lines = []
    for coin in trending[:5]:
        lines.append(f"- {coin.get('name', 'Unknown')} ({coin.get('symbol', '?')})")
    return "\n".join(lines) if lines else "No trending data available"


def _format_technical_indicators(tech_indicators: dict) -> str:
    """Format technical indicators into a concise readable string for the prompt"""
    if not tech_indicators or not isinstance(tech_indicators, dict):
        return "No technical data available"

    lines = []
    for symbol in ["BTC", "ETH", "SOL"]:
        ind = tech_indicators.get(symbol, {})
        if not ind or "error" in ind:
            lines.append(f"- {symbol}: Data unavailable")
            continue

        rsi = ind.get("rsi", "?")
        rsi_sig = ind.get("rsi_signal", "neutral")
        macd_hist = ind.get("macd", {}).get("histogram", 0)
        macd_sig = ind.get("macd_signal", "")
        macd_cross = ind.get("macd_crossover", "no_cross")
        ema_cross = ind.get("ema_crossover", "neutral")
        bb_sig = ind.get("bb_signal", "")
        momentum = ind.get("momentum_trend", "stable")

        cross_str = f" [{macd_cross.replace('_', ' ')}]" if macd_cross != "no_cross" else ""
        lines.append(
            f"- {symbol}: RSI={rsi} ({rsi_sig}) | "
            f"MACD histogram={macd_hist:+.2f}{cross_str} ({macd_sig}) | "
            f"EMA9/21 crossover={ema_cross} | "
            f"BB={bb_sig} | "
            f"Momentum={momentum}"
        )

    return "\n".join(lines) if lines else "No technical data available"


def _format_news_for_prompt(news: list) -> str:
    """Format news headlines for the prompt"""
    if not news or not isinstance(news, list):
        return "No recent news available"

    lines = []
    for i, article in enumerate(news[:8], 1):
        title = article.get("title", "")
        source = article.get("source", "")
        published_at = article.get("published_at", "")
        if title:
            meta = f"{source}, {published_at}" if source and published_at else source or published_at
            lines.append(f'{i}. "{title}" ({meta})')

    return "\n".join(lines) if lines else "No recent news available"
