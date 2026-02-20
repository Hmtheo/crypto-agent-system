"""
MCP Server for Crypto Agent System
Exposes crypto market data, AI analysis, and paper trading as Claude Desktop tools.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Add project root to path so we can import agents and paper_trading
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from agents.monitor import get_prices, get_market_data, get_news, get_price_history, run_monitor
from agents.analysis import analyze_market
from agents.advisory import get_recommendations
import paper_trading

app = Server("crypto-agent-system")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_crypto_prices",
            description="Get current prices for Bitcoin (BTC), Ethereum (ETH), and Solana (SOL) including 24h change, volume, and market cap.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_market_overview",
            description="Get overall crypto market statistics: total market cap, 24h volume, BTC/ETH dominance, and market cap change.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_trending_coins",
            description="Get currently trending coins on CoinGecko.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_price_history",
            description="Get historical price data for a specific coin.",
            inputSchema={
                "type": "object",
                "properties": {
                    "coin_id": {
                        "type": "string",
                        "description": "Coin identifier: 'bitcoin', 'ethereum', or 'solana'",
                        "enum": ["bitcoin", "ethereum", "solana"],
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days of history to fetch (default: 7)",
                        "default": 7,
                    },
                },
                "required": ["coin_id"],
            },
        ),
        Tool(
            name="analyze_crypto_market",
            description=(
                "Run AI-powered market analysis using Claude. Returns market sentiment, "
                "trend analysis for BTC/ETH/SOL, risk level, and a market summary."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_trade_recommendations",
            description=(
                "Get AI-powered paper trade recommendations for BTC, ETH, and SOL futures "
                "including direction (long/short/wait), leverage, entry price, take profit, "
                "and stop loss levels."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_portfolio",
            description="Get the current paper trading portfolio status including balance, open positions, and performance stats.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_portfolio_stats",
            description="Get detailed paper trading performance statistics: total trades, win rate, total PnL, and more.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="reset_portfolio",
            description="Reset the paper trading portfolio to a fresh state.",
            inputSchema={
                "type": "object",
                "properties": {
                    "initial_balance": {
                        "type": "number",
                        "description": "Starting balance in USD (default: 10000)",
                        "default": 10000.0,
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="execute_trade_recommendations",
            description=(
                "Run the full pipeline: fetch market data, analyze with AI, get trade "
                "recommendations, auto-execute paper trades, and update existing positions. "
                "Returns a complete summary of all actions taken."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "get_crypto_prices":
            result = await get_prices()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_market_overview":
            result = await get_market_data()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_trending_coins":
            result = await get_news()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_price_history":
            coin_id = arguments.get("coin_id", "bitcoin")
            days = arguments.get("days", 7)
            result = await get_price_history(coin_id, days)
            # Return a summary instead of all data points to keep output manageable
            summary = {
                "coin_id": coin_id,
                "days": days,
                "data_points": len(result),
                "first": result[0] if result else None,
                "last": result[-1] if result else None,
                "prices": result[-24:] if len(result) > 24 else result,  # last 24 points
            }
            return [TextContent(type="text", text=json.dumps(summary, indent=2))]

        elif name == "analyze_crypto_market":
            monitor_data = await run_monitor()
            analysis = await analyze_market(monitor_data)
            return [TextContent(type="text", text=json.dumps(analysis, indent=2))]

        elif name == "get_trade_recommendations":
            monitor_data = await run_monitor()
            analysis = await analyze_market(monitor_data)
            recommendations = await get_recommendations(monitor_data, analysis)
            return [TextContent(type="text", text=json.dumps(recommendations, indent=2))]

        elif name == "get_portfolio":
            result = paper_trading.get_portfolio()
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

        elif name == "get_portfolio_stats":
            result = paper_trading.get_performance_stats()
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

        elif name == "reset_portfolio":
            initial_balance = arguments.get("initial_balance", 10000.0)
            result = paper_trading.reset_portfolio(initial_balance)
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

        elif name == "execute_trade_recommendations":
            monitor_data = await run_monitor()
            analysis = await analyze_market(monitor_data)
            recommendations = await get_recommendations(monitor_data, analysis)
            current_prices = monitor_data.get("prices", {})
            opened_positions = paper_trading.auto_execute_recommendations(
                recommendations, current_prices
            )
            closed_positions = paper_trading.update_positions(current_prices)
            result = {
                "monitor": monitor_data,
                "analysis": analysis,
                "recommendations": recommendations,
                "opened_positions": opened_positions,
                "closed_positions": closed_positions,
                "portfolio": paper_trading.get_portfolio(),
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error running {name}: {str(e)}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
