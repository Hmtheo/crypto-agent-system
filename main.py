"""
Crypto Agent System - Main FastAPI Application
"""
import os
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional

# Load environment variables
load_dotenv()

# Import agents and trading system
from agents.monitor import run_monitor, get_prices, get_price_history, get_crypto_news
from agents.analysis import analyze_market
from agents.advisory import get_recommendations
import paper_trading
import database
from database import init_db

app = FastAPI(title="Crypto Agent System", version="1.0.0")

# Trust Railway's reverse proxy so request.url_for() generates https:// URLs
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# Session middleware (must be added before routes are evaluated)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SECRET_KEY", "dev-insecure-secret-change-me")
)

# Google OAuth client
oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup."""
    init_db()


# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# --- Auth dependency ---

def get_current_user(request: Request) -> dict:
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# --- Request models ---

class ResetPortfolioRequest(BaseModel):
    initial_balance: Optional[float] = 10000.0


class ClosePositionRequest(BaseModel):
    position_id: int
    close_price: float


# --- Auth routes ---

@app.get("/login")
async def login_page():
    """Serve the login page."""
    return FileResponse("static/login.html")


@app.get("/auth/google")
async def google_login(request: Request):
    """Redirect to Google OAuth consent screen."""
    redirect_uri = os.environ.get("OAUTH_REDIRECT_URI") or str(request.url_for("google_callback"))
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google/callback", name="google_callback")
async def google_callback(request: Request):
    """Handle Google OAuth callback, create session, redirect to dashboard."""
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        return RedirectResponse(url="/login")

    user_info = token.get("userinfo")
    if not user_info:
        return RedirectResponse(url="/login")

    user_id = database.get_or_create_user(
        google_id=user_info["sub"],
        email=user_info["email"],
        name=user_info.get("name"),
        picture=user_info.get("picture"),
    )

    request.session["user"] = {
        "id": user_id,
        "email": user_info["email"],
        "name": user_info.get("name"),
        "picture": user_info.get("picture"),
    }
    return RedirectResponse(url="/")


@app.get("/auth/logout")
async def logout(request: Request):
    """Clear session and redirect to login."""
    request.session.clear()
    return RedirectResponse(url="/login")


# --- App routes ---

@app.get("/")
async def root(request: Request):
    """Serve the main dashboard, or redirect to login if not authenticated."""
    if not request.session.get("user"):
        return RedirectResponse(url="/login")
    return FileResponse("static/index.html")


@app.get("/api/health")
async def health_check():
    """Health check endpoint — public, no auth required."""
    return {"status": "ok", "service": "crypto-agent-system"}


# --- Monitor Agent endpoints ---

@app.get("/api/monitor")
async def monitor(user: dict = Depends(get_current_user)):
    """Run the monitor agent to fetch current market data."""
    try:
        data = await run_monitor()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prices")
async def prices(user: dict = Depends(get_current_user)):
    """Get current prices only."""
    try:
        data = await get_prices()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/news")
async def news(user: dict = Depends(get_current_user)):
    """Get latest crypto news headlines."""
    try:
        articles = await get_crypto_news()
        return {"news": articles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history/{coin_id}")
async def price_history(coin_id: str, days: int = 7, user: dict = Depends(get_current_user)):
    """Get price history for a coin."""
    valid_coins = ["bitcoin", "ethereum", "solana"]
    if coin_id not in valid_coins:
        raise HTTPException(status_code=400, detail=f"Invalid coin. Use one of: {valid_coins}")
    try:
        data = await get_price_history(coin_id, days)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Analysis Agent endpoint ---

@app.get("/api/analyze")
async def analyze(user: dict = Depends(get_current_user)):
    """Run monitor and analysis agents."""
    try:
        monitor_data = await run_monitor()
        analysis = await analyze_market(monitor_data)
        return {
            "monitor": monitor_data,
            "analysis": analysis
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Advisory Agent endpoint ---

@app.get("/api/recommend")
async def recommend(user: dict = Depends(get_current_user)):
    """Run all agents and get trade recommendations."""
    try:
        monitor_data = await run_monitor()
        analysis = await analyze_market(monitor_data)
        performance_ctx = paper_trading.get_performance_context(user["id"])
        recommendations = await get_recommendations(monitor_data, analysis, performance_ctx)
        return {
            "monitor": monitor_data,
            "analysis": analysis,
            "recommendations": recommendations,
            "performance_context": performance_ctx,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Paper Trading endpoints ---

@app.get("/api/portfolio")
async def get_portfolio(user: dict = Depends(get_current_user)):
    """Get current paper trading portfolio."""
    return paper_trading.get_portfolio(user["id"])


@app.post("/api/portfolio/reset")
async def reset_portfolio(request: ResetPortfolioRequest, user: dict = Depends(get_current_user)):
    """Reset paper trading portfolio."""
    return paper_trading.reset_portfolio(user["id"], request.initial_balance)


@app.get("/api/portfolio/stats")
async def get_stats(user: dict = Depends(get_current_user)):
    """Get performance statistics."""
    return paper_trading.get_performance_stats(user["id"])


@app.post("/api/portfolio/update")
async def update_positions(user: dict = Depends(get_current_user)):
    """Update positions with current prices and check TP/SL."""
    try:
        current_prices = await get_prices()
        closed = paper_trading.update_positions(user["id"], current_prices)
        portfolio = paper_trading.get_portfolio(user["id"])
        return {
            "closed_positions": closed,
            "portfolio": portfolio
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/portfolio/close")
async def close_position(request: ClosePositionRequest, user: dict = Depends(get_current_user)):
    """Manually close a position."""
    result = paper_trading.close_position(
        user["id"],
        request.position_id,
        request.close_price,
        "manual"
    )
    if not result:
        raise HTTPException(status_code=404, detail="Position not found")
    return result


@app.post("/api/execute")
async def execute_recommendations(user: dict = Depends(get_current_user)):
    """Run all agents, get recommendations, and auto-execute trades."""
    try:
        monitor_data = await run_monitor()
        analysis = await analyze_market(monitor_data)
        performance_ctx = paper_trading.get_performance_context(user["id"])
        recommendations = await get_recommendations(monitor_data, analysis, performance_ctx)
        # Auto-execute
        current_prices = monitor_data.get("prices", {})
        opened_positions = paper_trading.auto_execute_recommendations(
            user["id"], recommendations, current_prices
        )
        # Also update existing positions
        closed_positions = paper_trading.update_positions(user["id"], current_prices)

        return {
            "monitor": monitor_data,
            "analysis": analysis,
            "recommendations": recommendations,
            "opened_positions": opened_positions,
            "closed_positions": closed_positions,
            "portfolio": paper_trading.get_portfolio(user["id"])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
