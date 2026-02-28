"""
Crypto Agent System - Main FastAPI Application
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

# Load environment variables
load_dotenv()

# DB, models, auth
from database import get_db, init_db
from models import User, Portfolio
from auth import (
    build_google_auth_url,
    exchange_code_for_token,
    get_google_user_info,
    create_access_token,
    generate_state,
    GOOGLE_CLIENT_ID,
)
from dependencies import get_current_user, get_current_portfolio

# Agents & trading
from agents.monitor import run_monitor, get_prices, get_price_history
from agents.analysis import analyze_market
from agents.advisory import get_recommendations
from paper_trading import PaperTrader


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Crypto Agent System", version="2.0.0", lifespan=lifespan)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ResetPortfolioRequest(BaseModel):
    initial_balance: Optional[float] = 10000.0


class ClosePositionRequest(BaseModel):
    position_id: str
    close_price: float


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return FileResponse("static/index.html")


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.get("/auth/google")
async def google_auth(response: Response):
    """Redirect the user to Google's OAuth consent screen."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")
    state = generate_state()
    auth_url = build_google_auth_url(state)
    redirect = RedirectResponse(url=auth_url)
    # Store state in a short-lived cookie to verify on callback
    redirect.set_cookie("oauth_state", state, max_age=600, httponly=True, samesite="lax")
    return redirect


@app.get("/auth/google/callback")
async def google_callback(
    code: str,
    state: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Google OAuth callback, create/update user, issue JWT."""
    stored_state = request.cookies.get("oauth_state")
    if not stored_state or stored_state != state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    try:
        token_data = await exchange_code_for_token(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {e}")

    try:
        user_info = await get_google_user_info(token_data["access_token"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch user info: {e}")

    google_sub = user_info.get("sub")
    email = user_info.get("email")
    if not google_sub or not email:
        raise HTTPException(status_code=400, detail="Incomplete user info from Google")

    # Upsert user
    result = await db.execute(select(User).where(User.google_sub == google_sub))
    user = result.scalar_one_or_none()

    if not user:
        # Check by email (user may have logged in via a different method previously)
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    if user:
        user.google_sub = google_sub
        user.name = user_info.get("name", user.name)
        user.picture = user_info.get("picture", user.picture)
    else:
        user = User(
            email=email,
            name=user_info.get("name"),
            picture=user_info.get("picture"),
            google_sub=google_sub,
        )
        db.add(user)

    await db.flush()

    # Ensure user has a default portfolio
    port_result = await db.execute(select(Portfolio).where(Portfolio.user_id == user.id))
    if not port_result.scalars().first():
        db.add(Portfolio(user_id=user.id))

    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": user.id, "email": user.email})

    # Redirect to frontend with token in URL fragment
    redirect = RedirectResponse(url=f"/#token={token}")
    redirect.delete_cookie("oauth_state")
    return redirect


@app.get("/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "picture": current_user.picture,
    }


# ---------------------------------------------------------------------------
# Health check (public)
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "crypto-agent-system",
        "auth": "google_oauth",
        "google_configured": bool(GOOGLE_CLIENT_ID),
    }


# ---------------------------------------------------------------------------
# Market data endpoints (protected)
# ---------------------------------------------------------------------------

@app.get("/api/monitor")
async def monitor(current_user: User = Depends(get_current_user)):
    try:
        return await run_monitor()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prices")
async def prices(current_user: User = Depends(get_current_user)):
    try:
        return await get_prices()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history/{coin_id}")
async def price_history(
    coin_id: str,
    days: int = 7,
    current_user: User = Depends(get_current_user),
):
    valid_coins = ["bitcoin", "ethereum", "solana"]
    if coin_id not in valid_coins:
        raise HTTPException(status_code=400, detail=f"Invalid coin. Use one of: {valid_coins}")
    try:
        return await get_price_history(coin_id, days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analyze")
async def analyze(current_user: User = Depends(get_current_user)):
    try:
        monitor_data = await run_monitor()
        analysis = await analyze_market(monitor_data)
        return {"monitor": monitor_data, "analysis": analysis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/recommend")
async def recommend(current_user: User = Depends(get_current_user)):
    try:
        monitor_data = await run_monitor()
        analysis = await analyze_market(monitor_data)
        recommendations = await get_recommendations(monitor_data, analysis)
        return {"monitor": monitor_data, "analysis": analysis, "recommendations": recommendations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Portfolio endpoints (protected, per-user)
# ---------------------------------------------------------------------------

@app.get("/api/portfolio")
async def get_portfolio(
    portfolio: Portfolio = Depends(get_current_portfolio),
    db: AsyncSession = Depends(get_db),
):
    trader = PaperTrader(db, portfolio.id)
    return await trader.get_portfolio()


@app.post("/api/portfolio/reset")
async def reset_portfolio(
    request: ResetPortfolioRequest,
    portfolio: Portfolio = Depends(get_current_portfolio),
    db: AsyncSession = Depends(get_db),
):
    trader = PaperTrader(db, portfolio.id)
    return await trader.reset_portfolio(request.initial_balance)


@app.get("/api/portfolio/stats")
async def get_stats(
    portfolio: Portfolio = Depends(get_current_portfolio),
    db: AsyncSession = Depends(get_db),
):
    trader = PaperTrader(db, portfolio.id)
    return await trader.get_performance_stats()


@app.post("/api/portfolio/update")
async def update_positions(
    portfolio: Portfolio = Depends(get_current_portfolio),
    db: AsyncSession = Depends(get_db),
):
    try:
        current_prices = await get_prices()
        trader = PaperTrader(db, portfolio.id)
        closed = await trader.update_positions(current_prices)
        portfolio_data = await trader.get_portfolio()
        return {"closed_positions": closed, "portfolio": portfolio_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/portfolio/close")
async def close_position(
    request: ClosePositionRequest,
    portfolio: Portfolio = Depends(get_current_portfolio),
    db: AsyncSession = Depends(get_db),
):
    trader = PaperTrader(db, portfolio.id)
    result = await trader.close_position(request.position_id, request.close_price, "manual")
    if not result:
        raise HTTPException(status_code=404, detail="Position not found")
    return result


@app.post("/api/execute")
async def execute_recommendations(
    portfolio: Portfolio = Depends(get_current_portfolio),
    db: AsyncSession = Depends(get_db),
):
    try:
        monitor_data = await run_monitor()
        analysis = await analyze_market(monitor_data)
        recommendations = await get_recommendations(monitor_data, analysis)
        current_prices = monitor_data.get("prices", {})

        trader = PaperTrader(db, portfolio.id)
        opened_positions = await trader.auto_execute_recommendations(recommendations, current_prices)
        closed_positions = await trader.update_positions(current_prices)

        return {
            "monitor": monitor_data,
            "analysis": analysis,
            "recommendations": recommendations,
            "opened_positions": opened_positions,
            "closed_positions": closed_positions,
            "portfolio": await trader.get_portfolio(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
