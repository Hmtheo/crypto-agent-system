"""
Paper Trading System - DB-backed, per-user portfolio isolation
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import Portfolio, Position, TradeHistory


class PaperTrader:
    """Manages paper trading for a single user portfolio."""

    def __init__(self, db: AsyncSession, portfolio_id: str):
        self.db = db
        self.portfolio_id = portfolio_id

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    async def _get_portfolio(self) -> Optional[Portfolio]:
        result = await self.db.execute(
            select(Portfolio).where(Portfolio.id == self.portfolio_id)
        )
        return result.scalar_one_or_none()

    def _pos_dict(self, p: Position) -> dict:
        return {
            "id": p.id,
            "symbol": p.symbol,
            "direction": p.direction,
            "entry_price": p.entry_price,
            "current_price": p.current_price,
            "leverage": p.leverage,
            "position_size": p.position_size,
            "margin_used": p.margin_used,
            "take_profit_price": p.take_profit_price,
            "stop_loss_price": p.stop_loss_price,
            "confidence": p.confidence,
            "reasoning": p.reasoning,
            "opened_at": p.opened_at.isoformat() if p.opened_at else None,
            "unrealized_pnl": p.unrealized_pnl,
            "unrealized_pnl_percent": p.unrealized_pnl_percent,
        }

    def _hist_dict(self, h: TradeHistory) -> dict:
        return {
            "id": h.id,
            "symbol": h.symbol,
            "direction": h.direction,
            "entry_price": h.entry_price,
            "close_price": h.close_price,
            "leverage": h.leverage,
            "position_size": h.position_size,
            "margin_used": h.margin_used,
            "take_profit_price": h.take_profit_price,
            "stop_loss_price": h.stop_loss_price,
            "confidence": h.confidence,
            "reasoning": h.reasoning,
            "opened_at": h.opened_at.isoformat() if h.opened_at else None,
            "closed_at": h.closed_at.isoformat() if h.closed_at else None,
            "close_reason": h.close_reason,
            "realized_pnl": h.realized_pnl,
            "realized_pnl_percent": h.realized_pnl_percent,
            "was_profitable": h.was_profitable,
            "hit_target": h.hit_target,
        }

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def get_portfolio(self) -> dict:
        portfolio = await self._get_portfolio()
        if not portfolio:
            return {}

        pos_result = await self.db.execute(
            select(Position).where(Position.portfolio_id == self.portfolio_id)
        )
        positions = pos_result.scalars().all()

        hist_result = await self.db.execute(
            select(TradeHistory)
            .where(TradeHistory.portfolio_id == self.portfolio_id)
            .order_by(TradeHistory.closed_at)
        )
        history = hist_result.scalars().all()

        total_trades = len(history)
        winning_trades = sum(1 for h in history if h.was_profitable)
        total_pnl = sum(h.realized_pnl or 0.0 for h in history)

        return {
            "balance": portfolio.balance,
            "initial_balance": portfolio.initial_balance,
            "positions": [self._pos_dict(p) for p in positions],
            "history": [self._hist_dict(h) for h in history],
            "stats": {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": total_trades - winning_trades,
                "total_pnl": total_pnl,
            },
        }

    async def open_position(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        leverage: int,
        take_profit_price: float,
        stop_loss_price: float,
        confidence: int,
        reasoning: str,
        position_size_percent: float = 10.0,
    ) -> dict:
        portfolio = await self._get_portfolio()
        if not portfolio:
            return {"error": "Portfolio not found"}

        margin_used = portfolio.balance * (position_size_percent / 100)
        if margin_used > portfolio.balance or portfolio.balance <= 0:
            return {"error": "Insufficient balance"}

        position_size = (margin_used * leverage) / entry_price

        position = Position(
            id=str(uuid.uuid4()),
            portfolio_id=self.portfolio_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            current_price=entry_price,
            leverage=leverage,
            position_size=position_size,
            margin_used=margin_used,
            take_profit_price=take_profit_price,
            stop_loss_price=stop_loss_price,
            confidence=confidence,
            reasoning=reasoning,
            opened_at=datetime.utcnow(),
            unrealized_pnl=0.0,
            unrealized_pnl_percent=0.0,
        )

        portfolio.balance -= margin_used
        self.db.add(position)
        await self.db.commit()
        await self.db.refresh(position)

        return self._pos_dict(position)

    async def update_positions(self, current_prices: dict) -> list:
        """Update P&L for all open positions; auto-close on TP/SL hit."""
        portfolio = await self._get_portfolio()
        if not portfolio:
            return []

        pos_result = await self.db.execute(
            select(Position).where(Position.portfolio_id == self.portfolio_id)
        )
        positions = pos_result.scalars().all()
        closed = []

        for pos in positions:
            price_data = current_prices.get(pos.symbol)
            if not price_data:
                continue

            current_price = price_data.get("price", pos.entry_price)
            pos.current_price = current_price

            if pos.direction == "long":
                pct = ((current_price - pos.entry_price) / pos.entry_price) * 100
            else:
                pct = ((pos.entry_price - current_price) / pos.entry_price) * 100

            pos.unrealized_pnl_percent = round(pct * pos.leverage, 2)
            pos.unrealized_pnl = round(pos.margin_used * (pos.unrealized_pnl_percent / 100), 2)

            # Check TP / SL
            close_reason = None
            if pos.direction == "long":
                if current_price >= pos.take_profit_price:
                    close_reason = "take_profit"
                elif current_price <= pos.stop_loss_price:
                    close_reason = "stop_loss"
            else:
                if current_price <= pos.take_profit_price:
                    close_reason = "take_profit"
                elif current_price >= pos.stop_loss_price:
                    close_reason = "stop_loss"

            if close_reason:
                record = await self._close_position_obj(pos, current_price, close_reason, portfolio)
                closed.append(record)

        await self.db.commit()
        return closed

    async def _close_position_obj(
        self,
        pos: Position,
        close_price: float,
        reason: str,
        portfolio: Portfolio,
    ) -> dict:
        if pos.direction == "long":
            pct = ((close_price - pos.entry_price) / pos.entry_price) * 100
        else:
            pct = ((pos.entry_price - close_price) / pos.entry_price) * 100

        leveraged_pct = pct * pos.leverage
        realized_pnl = round(pos.margin_used * (leveraged_pct / 100), 2)

        trade = TradeHistory(
            id=str(uuid.uuid4()),
            portfolio_id=self.portfolio_id,
            symbol=pos.symbol,
            direction=pos.direction,
            entry_price=pos.entry_price,
            close_price=close_price,
            leverage=pos.leverage,
            position_size=pos.position_size,
            margin_used=pos.margin_used,
            take_profit_price=pos.take_profit_price,
            stop_loss_price=pos.stop_loss_price,
            confidence=pos.confidence,
            reasoning=pos.reasoning,
            opened_at=pos.opened_at,
            closed_at=datetime.utcnow(),
            close_reason=reason,
            realized_pnl=realized_pnl,
            realized_pnl_percent=round(leveraged_pct, 2),
            was_profitable=realized_pnl > 0,
            hit_target=reason == "take_profit" and realized_pnl > 0,
        )

        portfolio.balance += pos.margin_used + realized_pnl
        self.db.add(trade)
        await self.db.delete(pos)
        return self._hist_dict(trade)

    async def close_position(self, position_id: str, close_price: float, reason: str = "manual") -> Optional[dict]:
        pos_result = await self.db.execute(
            select(Position).where(
                Position.id == position_id,
                Position.portfolio_id == self.portfolio_id,
            )
        )
        pos = pos_result.scalar_one_or_none()
        if not pos:
            return None

        portfolio = await self._get_portfolio()
        record = await self._close_position_obj(pos, close_price, reason, portfolio)
        await self.db.commit()
        return record

    async def reset_portfolio(self, initial_balance: float = 10000.0) -> dict:
        portfolio = await self._get_portfolio()
        if not portfolio:
            return {"error": "Portfolio not found"}

        pos_result = await self.db.execute(
            select(Position).where(Position.portfolio_id == self.portfolio_id)
        )
        for pos in pos_result.scalars().all():
            await self.db.delete(pos)

        hist_result = await self.db.execute(
            select(TradeHistory).where(TradeHistory.portfolio_id == self.portfolio_id)
        )
        for trade in hist_result.scalars().all():
            await self.db.delete(trade)

        portfolio.balance = initial_balance
        portfolio.initial_balance = initial_balance
        await self.db.commit()

        return await self.get_portfolio()

    async def get_performance_stats(self) -> dict:
        portfolio_data = await self.get_portfolio()
        stats = portfolio_data.get("stats", {})
        balance = portfolio_data.get("balance", 0)
        initial = portfolio_data.get("initial_balance", 10000.0)

        total_trades = stats.get("total_trades", 0)
        winning_trades = stats.get("winning_trades", 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        total_return = ((balance - initial) / initial * 100) if initial else 0.0

        return {
            "current_balance": round(balance, 2),
            "initial_balance": initial,
            "total_return_percent": round(total_return, 2),
            "total_pnl": round(stats.get("total_pnl", 0.0), 2),
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": stats.get("losing_trades", 0),
            "win_rate": round(win_rate, 1),
            "open_positions": len(portfolio_data.get("positions", [])),
            "history_count": len(portfolio_data.get("history", [])),
        }

    async def auto_execute_recommendations(self, recommendations: dict, current_prices: dict) -> list:
        opened = []

        pos_result = await self.db.execute(
            select(Position).where(Position.portfolio_id == self.portfolio_id)
        )
        existing_symbols = {p.symbol for p in pos_result.scalars().all()}

        for rec in recommendations.get("recommendations", []):
            if rec.get("action") == "wait":
                continue

            symbol = rec.get("symbol")
            if not symbol or symbol not in current_prices:
                continue

            if symbol in existing_symbols:
                continue

            price_data = current_prices[symbol]
            current_price = price_data.get("price") if isinstance(price_data, dict) else price_data
            if not current_price:
                continue

            position = await self.open_position(
                symbol=symbol,
                direction=rec.get("action", "long"),
                entry_price=current_price,
                leverage=min(rec.get("leverage", 1), 10),
                take_profit_price=rec.get("take_profit_price", current_price * 1.05),
                stop_loss_price=rec.get("stop_loss_price", current_price * 0.95),
                confidence=rec.get("confidence", 50),
                reasoning=rec.get("reasoning", "No reasoning provided"),
            )
            if "error" not in position:
                opened.append(position)
                existing_symbols.add(symbol)

        return opened
