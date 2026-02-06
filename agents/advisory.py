"""
Advisory Agent - Provides trade recommendations based on analysis
"""
import os
import json
from anthropic import Anthropic
from typing import Optional


def get_client() -> Anthropic:
    """Get Anthropic client"""
    return Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


async def get_recommendations(monitor_data: dict, analysis_data: dict) -> dict:
    """Generate trade recommendations based on market data and analysis"""
    client = get_client()

    prices = monitor_data.get("prices", {})

    prompt = f"""You are a crypto trading advisor for paper trading (simulated trades only - no real money).
Based on the market analysis, provide trade recommendations for BTC, ETH, and SOL perpetual futures.

CURRENT PRICES:
- BTC: ${prices.get('BTC', {}).get('price', 0):,.2f}
- ETH: ${prices.get('ETH', {}).get('price', 0):,.2f}
- SOL: ${prices.get('SOL', {}).get('price', 0):,.2f}

MARKET ANALYSIS:
{json.dumps(analysis_data, indent=2)}

For each coin, provide a recommendation in this exact JSON format:
{{
    "recommendations": [
        {{
            "symbol": "BTC",
            "action": "long" | "short" | "wait",
            "confidence": <number 0-100>,
            "leverage": <number 1-10>,
            "entry_price": <current price or null if wait>,
            "take_profit_price": <target price>,
            "take_profit_percent": <percent gain>,
            "stop_loss_price": <stop price>,
            "stop_loss_percent": <percent loss>,
            "reasoning": "<brief explanation>",
            "risk_reward_ratio": <number>
        }},
        {{
            "symbol": "ETH",
            ...
        }},
        {{
            "symbol": "SOL",
            ...
        }}
    ],
    "overall_market_stance": "aggressive" | "moderate" | "conservative" | "avoid",
    "portfolio_advice": "<brief overall advice>"
}}

Rules:
- Only recommend leverage 1-3x for low confidence (<50)
- Allow leverage 4-6x for medium confidence (50-75)
- Allow leverage 7-10x only for high confidence (>75)
- Risk/reward ratio should be at least 1.5
- Set reasonable take profit (2-15%) and stop loss (1-10%) based on volatility
- If market is too risky, recommend "wait" with null prices

Respond ONLY with the JSON, no other text."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = response.content[0].text.strip()

    # Parse JSON from response
    try:
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        recommendations = json.loads(response_text)
    except json.JSONDecodeError:
        recommendations = {
            "recommendations": [],
            "overall_market_stance": "avoid",
            "portfolio_advice": "Could not generate recommendations. Please try again.",
            "error": "Could not parse structured response"
        }

    return recommendations
