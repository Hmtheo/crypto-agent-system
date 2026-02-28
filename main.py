"""
Crypto Agent System - Main FastAPI Application
"""
import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional

# Load environment variables
load_dotenv()

# Import agents and trading system
from agents.monitor import run_monitor, get_prices, get_price_history
from agents.analysis import analyze_market
from agents.advisory import get_recommendations
import paper_trading
from database import init_db

app = FastAPI(title="Crypto Agent System", version="1.0.0")


@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup"""
    init_db()


# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# Request models
class ResetPortfolioRequest(BaseModel):
    initial_balance: Optional[float] = 10000.0


class ClosePositionRequest(BaseModel):
    position_id: int
    close_price: float


# Routes

@app.get("/")
async def root():
    """Serve the main dashboard"""
    return FileResponse("static/index.html")


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "crypto-agent-system"}


# Monitor Agent endpoints

@app.get("/api/monitor")
async def monitor():
    """Run the monitor agent to fetch current market data"""
    try:
        data = await run_monitor()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prices")
async def prices():
    """Get current prices only"""
    try:
        data = await get_prices()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history/{coin_id}")
async def price_history(coin_id: str, days: int = 7):
    """Get price history for a coin"""
    valid_coins = ["bitcoin", "ethereum", "solana"]
    if coin_id not in valid_coins:
        raise HTTPException(status_code=400, detail=f"Invalid coin. Use one of: {valid_coins}")
    try:
        data = await get_price_history(coin_id, days)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Analysis Agent endpoint

@app.get("/api/analyze")
async def analyze():
    """Run monitor and analysis agents"""
    try:
        # First get monitor data
        monitor_data = await run_monitor()
        # Then analyze it
        analysis = await analyze_market(monitor_data)
        return {
            "monitor": monitor_data,
            "analysis": analysis
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Advisory Agent endpoint

@app.get("/api/recommend")
async def recommend():
    """Run all agents and get trade recommendations"""
    try:
        # Get monitor data
        monitor_data = await run_monitor()
        # Analyze it
        analysis = await analyze_market(monitor_data)
        # Get recommendations
        recommendations = await get_recommendations(monitor_data, analysis)
        return {
            "monitor": monitor_data,
            "analysis": analysis,
            "recommendations": recommendations
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Paper Trading endpoints

@app.get("/api/portfolio")
async def get_portfolio():
    """Get current paper trading portfolio"""
    return paper_trading.get_portfolio()


@app.post("/api/portfolio/reset")
async def reset_portfolio(request: ResetPortfolioRequest):
    """Reset paper trading portfolio"""
    return paper_trading.reset_portfolio(request.initial_balance)


@app.get("/api/portfolio/stats")
async def get_stats():
    """Get performance statistics"""
    return paper_trading.get_performance_stats()


@app.post("/api/portfolio/update")
async def update_positions():
    """Update positions with current prices and check TP/SL"""
    try:
        current_prices = await get_prices()
        closed = paper_trading.update_positions(current_prices)
        portfolio = paper_trading.get_portfolio()
        return {
            "closed_positions": closed,
            "portfolio": portfolio
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/portfolio/close")
async def close_position(request: ClosePositionRequest):
    """Manually close a position"""
    result = paper_trading.close_position(
        request.position_id,
        request.close_price,
        "manual"
    )
    if not result:
        raise HTTPException(status_code=404, detail="Position not found")
    return result


@app.post("/api/execute")
async def execute_recommendations():
    """Run all agents, get recommendations, and auto-execute trades"""
    try:
        # Get monitor data
        monitor_data = await run_monitor()
        # Analyze it
        analysis = await analyze_market(monitor_data)
        # Get recommendations
        recommendations = await get_recommendations(monitor_data, analysis)
        # Auto-execute
        current_prices = monitor_data.get("prices", {})
        opened_positions = paper_trading.auto_execute_recommendations(
            recommendations, current_prices
        )
        # Also update existing positions
        closed_positions = paper_trading.update_positions(current_prices)

        return {
            "monitor": monitor_data,
            "analysis": analysis,
            "recommendations": recommendations,
            "opened_positions": opened_positions,
            "closed_positions": closed_positions,
            "portfolio": paper_trading.get_portfolio()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
