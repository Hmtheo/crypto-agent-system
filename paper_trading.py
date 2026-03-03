"""
Paper Trading System - Simulated trading with fake money
"""
from datetime import datetime
from typing import Optional
from database import get_cursor, get_user_portfolio_id


def _row_to_position(row) -> dict:
    """Convert a DB row to the dict format used by the API."""
    d = dict(row)
    for key in ("opened_at", "closed_at"):
        if key in d and isinstance(d[key], datetime):
            d[key] = d[key].isoformat()
    return d


def get_portfolio(user_id: int) -> dict:
    """Get current portfolio status for a user."""
    portfolio_id = get_user_portfolio_id(user_id)

    with get_cursor() as cur:
        cur.execute("SELECT * FROM portfolio WHERE id = %s", (portfolio_id,))
        port = dict(cur.fetchone())

        cur.execute("SELECT * FROM positions WHERE user_id = %s ORDER BY id", (user_id,))
        positions = [_row_to_position(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM trade_history WHERE user_id = %s ORDER BY closed_at", (user_id,))
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


def reset_portfolio(user_id: int, initial_balance: float = 10000.0) -> dict:
    """Reset a user's portfolio to initial state."""
    portfolio_id = get_user_portfolio_id(user_id)

    with get_cursor() as cur:
        cur.execute("DELETE FROM trade_history WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM positions WHERE user_id = %s", (user_id,))
        cur.execute("""
            UPDATE portfolio
            SET balance         = %s,
                initial_balance = %s,
                total_trades    = 0,
                winning_trades  = 0,
                losing_trades   = 0,
                total_pnl       = 0.0
            WHERE id = %s
        """, (initial_balance, initial_balance, portfolio_id))

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
    user_id: int,
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
    """Open a new paper trading position for a user."""
    portfolio_id = get_user_portfolio_id(user_id)

    with get_cursor() as cur:
        cur.execute("SELECT balance FROM portfolio WHERE id = %s", (portfolio_id,))
        balance = cur.fetchone()["balance"]

        # Calculate position size
        position_value = balance * (position_size_percent / 100)
        margin_used    = position_value
        position_size  = (position_value * leverage) / entry_price
        opened_at      = datetime.utcnow()

        cur.execute("""
            INSERT INTO positions
                (user_id, symbol, direction, entry_price, current_price, leverage,
                 position_size, margin_used, take_profit_price, stop_loss_price,
                 confidence, reasoning, opened_at,
                 unrealized_pnl, unrealized_pnl_percent)
            VALUES
                (%s, %s, %s, %s, %s, %s,
                 %s, %s, %s, %s,
                 %s, %s, %s,
                 0.0, 0.0)
            RETURNING *
        """, (
            user_id, symbol, direction, entry_price, entry_price, leverage,
            position_size, margin_used, take_profit_price, stop_loss_price,
            confidence, reasoning, opened_at
        ))
        position = _row_to_position(cur.fetchone())

        cur.execute("""
            UPDATE portfolio SET balance = balance - %s WHERE id = %s
        """, (margin_used, portfolio_id))

    return position


def update_positions(user_id: int, current_prices: dict) -> list:
    """Update all positions for a user with current prices and check for TP/SL."""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM positions WHERE user_id = %s", (user_id,))
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
                WHERE id = %s AND user_id = %s
            """, (current_price, unrealized_pnl, leveraged_pnl_percent, position["id"], user_id))

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
            closed = close_position(user_id, position["id"], current_price, close_reason)
            if closed:
                closed_positions.append(closed)

    return closed_positions


def close_position(user_id: int, position_id: int, close_price: float, reason: str = "manual") -> Optional[dict]:
    """Close a position for a user and record in history."""
    portfolio_id = get_user_portfolio_id(user_id)

    with get_cursor() as cur:
        cur.execute("SELECT * FROM positions WHERE id = %s AND user_id = %s", (position_id, user_id))
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
                (id, user_id, symbol, direction, entry_price, close_price, current_price,
                 leverage, position_size, margin_used,
                 take_profit_price, stop_loss_price, confidence, reasoning,
                 opened_at, closed_at,
                 unrealized_pnl, unrealized_pnl_percent,
                 realized_pnl, realized_pnl_percent,
                 close_reason, was_profitable, hit_target)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s,
                 %s, %s, %s,
                 %s, %s, %s, %s,
                 %s, %s,
                 %s, %s,
                 %s, %s,
                 %s, %s, %s)
            RETURNING *
        """, (
            position["id"], user_id, position["symbol"], position["direction"],
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

        cur.execute("DELETE FROM positions WHERE id = %s AND user_id = %s", (position_id, user_id))

        cur.execute("""
            UPDATE portfolio
            SET balance        = balance + %s,
                total_trades   = total_trades + 1,
                total_pnl      = total_pnl + %s,
                winning_trades = winning_trades + CASE WHEN %s > 0 THEN 1 ELSE 0 END,
                losing_trades  = losing_trades  + CASE WHEN %s <= 0 THEN 1 ELSE 0 END
            WHERE id = %s
        """, (
            position["margin_used"] + realized_pnl,
            realized_pnl,
            realized_pnl,
            realized_pnl,
            portfolio_id
        ))

    return history_record


def get_performance_stats(user_id: int) -> dict:
    """Get overall performance statistics for a user."""
    portfolio_id = get_user_portfolio_id(user_id)

    with get_cursor() as cur:
        cur.execute("SELECT * FROM portfolio WHERE id = %s", (portfolio_id,))
        port = dict(cur.fetchone())
        cur.execute("SELECT COUNT(*) AS cnt FROM positions WHERE user_id = %s", (user_id,))
        open_count = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM trade_history WHERE user_id = %s", (user_id,))
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


def get_performance_context(user_id: int, limit: int = 10) -> dict:
    """
    Summarise recent closed-trade outcomes for the advisory agent feedback loop.
    Returns a structured dict the advisory prompt can reason about.
    """
    data = get_portfolio(user_id)
    history = data.get("history", [])
    stats = data.get("stats", {})

    if not history:
        return {"has_history": False, "total_closed_trades": 0}

    total_trades = stats.get("total_trades", 0)
    winning_trades = stats.get("winning_trades", 0)
    overall_win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else None

    # Build per-symbol stats from all history
    by_symbol: dict = {}
    for trade in history:
        sym = trade["symbol"]
        if sym not in by_symbol:
            by_symbol[sym] = {"wins": 0, "losses": 0, "all_trades": []}
        if trade.get("was_profitable"):
            by_symbol[sym]["wins"] += 1
        else:
            by_symbol[sym]["losses"] += 1
        by_symbol[sym]["all_trades"].append(trade)

    per_symbol = {}
    for sym, sym_data in by_symbol.items():
        total = sym_data["wins"] + sym_data["losses"]
        win_rate = (sym_data["wins"] / total * 100) if total > 0 else None
        recent_3 = sym_data["all_trades"][-3:]
        per_symbol[sym] = {
            "total_trades": total,
            "win_rate": win_rate,
            "recent_trades": [
                {
                    "direction": t["direction"],
                    "confidence": t.get("confidence", 50),
                    "was_profitable": t["was_profitable"],
                    "close_reason": t["close_reason"],
                    "realized_pnl_percent": round(t.get("realized_pnl_percent", 0), 1),
                }
                for t in recent_3
            ],
        }

    # Detect repeating patterns (e.g. consecutive SL hits per symbol+direction)
    patterns = []
    for sym, sym_data in by_symbol.items():
        for direction in ["long", "short"]:
            dir_trades = [t for t in sym_data["all_trades"][-5:] if t["direction"] == direction]
            if len(dir_trades) >= 2:
                sl_count = sum(1 for t in dir_trades[-3:] if t["close_reason"] == "stop_loss")
                tp_count = sum(1 for t in dir_trades[-3:] if t["close_reason"] == "take_profit")
                window = min(3, len(dir_trades))
                if sl_count >= 2:
                    patterns.append(
                        f"{sym} {direction}s hitting stop loss {sl_count}/{window} recent trades"
                    )
                elif tp_count >= 2:
                    patterns.append(
                        f"{sym} {direction}s hitting take profit {tp_count}/{window} recent trades — momentum strong"
                    )

    recent_5 = [
        {
            "symbol": t["symbol"],
            "direction": t["direction"],
            "confidence": t.get("confidence", 50),
            "was_profitable": t["was_profitable"],
            "close_reason": t["close_reason"],
            "realized_pnl_percent": round(t.get("realized_pnl_percent", 0), 1),
        }
        for t in history[-5:]
    ]

    return {
        "has_history": True,
        "total_closed_trades": total_trades,
        "overall_win_rate": overall_win_rate,
        "overall_stats": {
            "total_pnl": stats.get("total_pnl", 0),
            "winning_trades": winning_trades,
            "losing_trades": stats.get("losing_trades", 0),
        },
        "per_symbol": per_symbol,
        "recent_trades": recent_5,
        "patterns": patterns,
    }


def auto_execute_recommendations(user_id: int, recommendations: dict, current_prices: dict) -> list:
    """Automatically open positions based on advisory recommendations for a user."""
    opened = []

    for rec in recommendations.get("recommendations", []):
        if rec.get("action") == "wait":
            continue

        symbol = rec.get("symbol")
        if not symbol or symbol not in current_prices:
            continue

        # Check if user already has a position for this symbol
        with get_cursor() as cur:
            cur.execute(
                "SELECT id FROM positions WHERE symbol = %s AND user_id = %s LIMIT 1",
                (symbol, user_id)
            )
            if cur.fetchone():
                continue

        current_price = current_prices[symbol].get("price")
        if not current_price:
            continue

        position = open_position(
            user_id=user_id,
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
