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


async def get_recommendations(
    monitor_data: dict,
    analysis_data: dict,
    performance_context: dict = None,
) -> dict:
    """Generate trade recommendations based on market data, analysis, and past performance"""
    client = get_client()

    prices = monitor_data.get("prices", {})
    tech_indicators = monitor_data.get("technical_indicators", {})

    performance_section = ""
    if performance_context and performance_context.get("has_history"):
        performance_section = f"""
RECENT TRADING PERFORMANCE — adapt your recommendations based on what is actually working:
{_format_performance_context(performance_context)}
"""

    prompt = f"""You are a crypto trading advisor for paper trading (simulated trades only - no real money).
Based on the market analysis and recent performance data, provide adaptive trade recommendations for BTC, ETH, and SOL perpetual futures.

CURRENT PRICES:
- BTC: ${prices.get('BTC', {}).get('price', 0):,.2f}
- ETH: ${prices.get('ETH', {}).get('price', 0):,.2f}
- SOL: ${prices.get('SOL', {}).get('price', 0):,.2f}

TECHNICAL LEVELS (use for precise TP/SL placement):
{_format_technical_levels(tech_indicators)}

MARKET ANALYSIS:
{json.dumps(analysis_data, indent=2)}
{performance_section}
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
            "reasoning": "<explanation covering signal rationale AND why you chose these specific TP/SL levels>",
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
- Set TP/SL based on market structure — use BB levels and EMA support/resistance as natural targets:
  - Long TP: target BB upper band or nearest resistance; SL: below EMA21 or BB middle
  - Short TP: target BB lower band or nearest support; SL: above EMA21 or BB middle
- Risk/reward ratio must reflect actual market conditions — do NOT default to a fixed floor:
  - Strong trend (RSI 55-65, MACD bullish crossover, price above EMA21): target R:R 2.5-4.0, widen TP
  - Choppy/ranging market (RSI 45-55, mixed signals): target R:R 1.8-2.5, tighten both TP and SL
  - Breakout move (BB width expanding, RSI at extremes): asymmetric TP 8-15%, SL 2-4%, R:R 3.0+
  - Overbought (RSI >70): if long, either tighten TP sharply or recommend wait; prefer shorts
  - Oversold (RSI <30): if short, prefer wait or tight TP; favor longs with generous TP
- If recent performance shows repeated SL hits on a direction: require confidence >80 or recommend "wait" for that symbol
- If market signals are unclear or conflicting, recommend "wait" with null prices

Respond ONLY with the JSON, no other text."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = response.content[0].text.strip()

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
            "error": "Could not parse structured response",
        }

    return recommendations


def _format_technical_levels(tech_indicators: dict) -> str:
    """Format BB + EMA levels per symbol for TP/SL calibration"""
    if not tech_indicators:
        return "Technical levels unavailable"

    lines = []
    for symbol in ["BTC", "ETH", "SOL"]:
        ind = tech_indicators.get(symbol, {})
        if not ind or "error" in ind:
            lines.append(f"- {symbol}: unavailable")
            continue

        bb = ind.get("bollinger_bands", {})
        ema9 = ind.get("ema9")
        ema21 = ind.get("ema21")
        rsi = ind.get("rsi", "?")
        rsi_sig = ind.get("rsi_signal", "")
        bb_sig = ind.get("bb_signal", "")

        lines.append(
            f"- {symbol}: "
            f"BB_lower=${bb.get('lower', 0):,.2f} | BB_mid=${bb.get('middle', 0):,.2f} | BB_upper=${bb.get('upper', 0):,.2f} | "
            f"EMA9=${ema9:,.2f} | EMA21=${ema21:,.2f} | "
            f"RSI={rsi} ({rsi_sig}) | BB_position={bb_sig}"
        )

    return "\n".join(lines) if lines else "Technical levels unavailable"


def _format_performance_context(ctx: dict) -> str:
    """Format trading performance context for the advisory prompt"""
    if not ctx or not ctx.get("has_history"):
        return "No trading history yet."

    total = ctx.get("total_closed_trades", 0)
    wr = ctx.get("overall_win_rate")
    wr_str = f"{wr:.0f}%" if wr is not None else "N/A"

    lines = [f"Overall: {wr_str} win rate ({total} closed trades)"]

    per_symbol = ctx.get("per_symbol", {})
    for symbol in ["BTC", "ETH", "SOL"]:
        sym = per_symbol.get(symbol)
        if not sym:
            lines.append(f"- {symbol}: No trades yet")
            continue

        sym_wr = sym.get("win_rate")
        sym_wr_str = f"{sym_wr:.0f}%" if sym_wr is not None else "N/A"
        recent = sym.get("recent_trades", [])
        recent_parts = []
        for t in recent:
            outcome = "TP" if t["close_reason"] == "take_profit" else ("SL" if t["close_reason"] == "stop_loss" else "MANUAL")
            recent_parts.append(f"{t['direction'].upper()} {outcome}({t['realized_pnl_percent']:+.1f}%)")
        recent_str = " → ".join(recent_parts) if recent_parts else "none"
        lines.append(f"- {symbol}: {sym_wr_str} win rate | last trades: {recent_str}")

    patterns = ctx.get("patterns", [])
    if patterns:
        lines.append("")
        lines.append("Detected patterns:")
        for p in patterns:
            lines.append(f"  ⚠ {p}")

    lines.extend([
        "",
        "Adaptation instructions:",
        "- Symbol+direction with 2+ consecutive SL hits: require confidence >80 OR recommend 'wait'",
        "- Frequent SL triggers overall: market is choppier than modeled — widen stops 1-2%, drop leverage 1x",
        "- Frequent TP hits: momentum is strong — use wider TP (10-15%) for higher R:R",
        "- Recalibrate confidence scores against recent accuracy; overconfident calls that lost should score lower",
    ])

    return "\n".join(lines)
