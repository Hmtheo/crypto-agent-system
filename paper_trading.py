"""
Paper Trading System - Simulated trading with fake money
"""
import os
from datetime import datetime
from typing import Optional
from database import get_cursor


def _row_to_position(row) -> dict:
    """Convert a DB row to the dict format used by the API."""
    d = dict(row)
    for key in ("opened_at", "closed_at"):
        if key in d and isinstance(d[key], datetime):
            d[key] = d[key].isoformat()
    return d


def get_portfolio() -> dict:
    """Get current portfolio status"""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM portfolio WHERE id = 1")
        port = dict(cur.fetchone())

        cur.execute("SELECT * FROM positions ORDER BY id")
        positions = [_row_to_position(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM trade_history ORDER BY closed_at")
        history = [_row_to_position(r) for r in cur.fetchall()]

    return {
        "balance": port["balance"],
        "initial_balance": port["initial_balance"],
        "positions": positions,
        "history": history,
        "stats": {
            "total_trades":   port["total_trades"],
            "winning_trades": port["winning_trades"],
            "losing_trades":  port["losing_trades"],
            "total_pnl":      port["total_pnl"],
        }
    }


def reset_portfolio(initial_balance: float = 10000.0) -> dict:
    """Reset portfolio to initial state"""
    with get_cursor() as cur:
        cur.execute("DELETE FROM trade_history")
        cur.execute("DELETE FROM positions")
        cur.execute("""
            UPDATE portfolio
            SET balance         = %s,
                initial_balance = %s,
                total_trades    = 0,
                winning_trades  = 0,
                losing_trades   = 0,
                total_pnl       = 0.0
            WHERE id = 1
        """, (initial_balance, initial_balance))

    return {
        "balance": initial_balance,
        "initial_balance": initial_balance,
        "positions": [],
        "history": [],
        "stats": {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0
        }
    }


def open_position(
    symbol: str,
    direction: str,  # "long" or "short"
    entry_price: float,
    leverage: int,
    take_profit_price: float,
    stop_loss_price: float,
    confidence: int,
    reasoning: str,
    position_size_percent: float = 10.0  # Use 10% of balance per trade
) -> dict:
    """Open a new paper trading position"""
    with get_cursor() as cur:
        cur.execute("SELECT balance FROM portfolio WHERE id = 1")
        balance = cur.fetchone()["balance"]

        # Calculate position size
        position_value = balance * (position_size_percent / 100)
        margin_used    = position_value
        position_size  = (position_value * leverage) / entry_price
        opened_at      = datetime.utcnow()

        cur.execute("""
            INSERT INTO positions
                (symbol, direction, entry_price, current_price, leverage,
                 position_size, margin_used, take_profit_price, stop_loss_price,
                 confidence, reasoning, opened_at,
                 unrealized_pnl, unrealized_pnl_percent)
            VALUES
                (%s, %s, %s, %s, %s,
                 %s, %s, %s, %s,
                 %s, %s, %s,
                 0.0, 0.0)
            RETURNING *
        """, (
            symbol, direction, entry_price, entry_price, leverage,
            position_size, margin_used, take_profit_price, stop_loss_price,
            confidence, reasoning, opened_at
        ))
        position = _row_to_position(cur.fetchone())

        cur.execute("""
            UPDATE portfolio SET balance = balance - %s WHERE id = 1
        """, (margin_used,))

    return position


def update_positions(current_prices: dict) -> list:
    """Update all positions with current prices and check for TP/SL"""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM positions")
        positions = [_row_to_position(r) for r in cur.fetchall()]

    closed_positions = []

    for position in positions:
        symbol = position["symbol"]
        if symbol not in current_prices:
            continue

        current_price = current_prices[symbol].get("price", position["entry_price"])

        # Calculate PnL
        if position["direction"] == "long":
            price_change_percent = ((current_price - position["entry_price"]) / position["entry_price"]) * 100
        else:  # short
            price_change_percent = ((position["entry_price"] - current_price) / position["entry_price"]) * 100

        leveraged_pnl_percent = price_change_percent * position["leverage"]
        unrealized_pnl        = position["margin_used"] * (leveraged_pnl_percent / 100)

        with get_cursor() as cur:
            cur.execute("""
                UPDATE positions
                SET current_price          = %s,
                    unrealized_pnl         = %s,
                    unrealized_pnl_percent = %s
                WHERE id = %s
            """, (current_price, unrealized_pnl, leveraged_pnl_percent, position["id"]))

        # Check take profit / stop loss
        should_close = False
        close_reason = ""

        if position["direction"] == "long":
            if current_price >= position["take_profit_price"]:
                should_close, close_reason = True, "take_profit"
            elif current_price <= position["stop_loss_price"]:
                should_close, close_reason = True, "stop_loss"
        else:  # short
            if current_price <= position["take_profit_price"]:
                should_close, close_reason = True, "take_profit"
            elif current_price >= position["stop_loss_price"]:
                should_close, close_reason = True, "stop_loss"

        if should_close:
            closed = close_position(position["id"], current_price, close_reason)
            if closed:
                closed_positions.append(closed)

    return closed_positions


def close_position(position_id: int, close_price: float, reason: str = "manual") -> Optional[dict]:
    """Close a position and record in history"""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM positions WHERE id = %s", (position_id,))
        row = cur.fetchone()
        if not row:
            return None
        position = _row_to_position(row)

    # Calculate final PnL
    if position["direction"] == "long":
        price_change_percent = ((close_price - position["entry_price"]) / position["entry_price"]) * 100
    else:
        price_change_percent = ((position["entry_price"] - close_price) / position["entry_price"]) * 100

    leveraged_pnl_percent = price_change_percent * position["leverage"]
    realized_pnl          = position["margin_used"] * (leveraged_pnl_percent / 100)
    closed_at             = datetime.utcnow()
    was_profitable        = realized_pnl > 0
    hit_target            = reason == "take_profit" and realized_pnl > 0

    with get_cursor() as cur:
        # Insert into history, delete from positions, update balance — all one transaction
        cur.execute("""
            INSERT INTO trade_history
                (id, symbol, direction, entry_price, close_price, current_price,
                 leverage, position_size, margin_used,
                 take_profit_price, stop_loss_price, confidence, reasoning,
                 opened_at, closed_at,
                 unrealized_pnl, unrealized_pnl_percent,
                 realized_pnl, realized_pnl_percent,
                 close_reason, was_profitable, hit_target)
            VALUES
                (%s, %s, %s, %s, %s, %s,
                 %s, %s, %s,
                 %s, %s, %s, %s,
                 %s, %s,
                 %s, %s,
                 %s, %s,
                 %s, %s, %s)
            RETURNING *
        """, (
            position["id"], position["symbol"], position["direction"],
            position["entry_price"], close_price, close_price,
            position["leverage"], position["position_size"], position["margin_used"],
            position["take_profit_price"], position["stop_loss_price"],
            position["confidence"], position["reasoning"],
            position["opened_at"], closed_at,
            position["unrealized_pnl"], position["unrealized_pnl_percent"],
            realized_pnl, leveraged_pnl_percent,
            reason, was_profitable, hit_target
        ))
        history_record = _row_to_position(cur.fetchone())

        cur.execute("DELETE FROM positions WHERE id = %s", (position_id,))

        cur.execute("""
            UPDATE portfolio
            SET balance        = balance + %s,
                total_trades   = total_trades + 1,
                total_pnl      = total_pnl + %s,
                winning_trades = winning_trades + CASE WHEN %s > 0 THEN 1 ELSE 0 END,
                losing_trades  = losing_trades  + CASE WHEN %s <= 0 THEN 1 ELSE 0 END
            WHERE id = 1
        """, (
            position["margin_used"] + realized_pnl,
            realized_pnl,
            realized_pnl,
            realized_pnl
        ))

    return history_record


def get_performance_stats() -> dict:
    """Get overall performance statistics"""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM portfolio WHERE id = 1")
        port = dict(cur.fetchone())
        cur.execute("SELECT COUNT(*) AS cnt FROM positions")
        open_count = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM trade_history")
        history_count = cur.fetchone()["cnt"]

    win_rate = 0.0
    if port["total_trades"] > 0:
        win_rate = (port["winning_trades"] / port["total_trades"]) * 100

    total_return = ((port["balance"] - port["initial_balance"]) / port["initial_balance"]) * 100

    return {
        "current_balance":      port["balance"],
        "initial_balance":      port["initial_balance"],
        "total_return_percent": total_return,
        "total_pnl":            port["total_pnl"],
        "total_trades":         port["total_trades"],
        "winning_trades":       port["winning_trades"],
        "losing_trades":        port["losing_trades"],
        "win_rate":             win_rate,
        "open_positions":       open_count,
        "history_count":        history_count,
    }


def auto_execute_recommendations(recommendations: dict, current_prices: dict) -> list:
    """Automatically open positions based on advisory recommendations"""
    opened = []

    for rec in recommendations.get("recommendations", []):
        if rec.get("action") == "wait":
            continue

        symbol = rec.get("symbol")
        if not symbol or symbol not in current_prices:
            continue

        # Check if we already have a position for this symbol
        with get_cursor() as cur:
            cur.execute("SELECT id FROM positions WHERE symbol = %s LIMIT 1", (symbol,))
            if cur.fetchone():
                continue

        current_price = current_prices[symbol].get("price")
        if not current_price:
            continue

        position = open_position(
            symbol=symbol,
            direction=rec.get("action", "long"),
            entry_price=current_price,
            leverage=min(rec.get("leverage", 1), 10),  # Cap at 10x
            take_profit_price=rec.get("take_profit_price", current_price * 1.05),
            stop_loss_price=rec.get("stop_loss_price", current_price * 0.95),
            confidence=rec.get("confidence", 50),
            reasoning=rec.get("reasoning", "No reasoning provided")
        )
        opened.append(position)

    return opened
