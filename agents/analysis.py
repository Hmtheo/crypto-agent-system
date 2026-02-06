"""
Analysis Agent - Analyzes market data and identifies trends using Claude
"""
import os
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

    prompt = f"""You are a crypto market analyst. Analyze the following market data and provide insights.

CURRENT PRICES:
{_format_prices(prices)}

MARKET OVERVIEW:
- Total Market Cap: ${market.get('total_market_cap', 0):,.0f}
- 24h Volume: ${market.get('total_volume', 0):,.0f}
- BTC Dominance: {market.get('btc_dominance', 0):.1f}%
- ETH Dominance: {market.get('eth_dominance', 0):.1f}%
- Market Cap Change 24h: {market.get('market_cap_change_24h', 0):.2f}%

TRENDING COINS:
{_format_trending(trending)}

Provide analysis in the following JSON format:
{{
    "market_sentiment": "bullish" | "bearish" | "neutral",
    "sentiment_score": <number from -100 to 100>,
    "btc_analysis": {{
        "trend": "up" | "down" | "sideways",
        "strength": "strong" | "moderate" | "weak",
        "key_factors": ["factor1", "factor2"]
    }},
    "eth_analysis": {{
        "trend": "up" | "down" | "sideways",
        "strength": "strong" | "moderate" | "weak",
        "key_factors": ["factor1", "factor2"]
    }},
    "sol_analysis": {{
        "trend": "up" | "down" | "sideways",
        "strength": "strong" | "moderate" | "weak",
        "key_factors": ["factor1", "factor2"]
    }},
    "market_summary": "<2-3 sentence summary>",
    "risk_level": "low" | "medium" | "high"
}}

Respond ONLY with the JSON, no other text."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    # Parse the response
    response_text = response.content[0].text.strip()

    # Try to parse JSON from response
    import json
    try:
        # Handle potential markdown code blocks
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
