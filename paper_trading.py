"""
Paper Trading System - Simulated trading with fake money
"""
import json
import os
from datetime import datetime
from typing import Optional
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "paper_trades.json"


def _load_data() -> dict:
    """Load paper trading data from file"""
    if DATA_FILE.exists():
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "balance": 10000.0,
        "initial_balance": 10000.0,
        "positions": [],
        "history": [],
        "stats": {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0
        }
    }


def _save_data(data: dict):
    """Save paper trading data to file"""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def get_portfolio() -> dict:
    """Get current portfolio status"""
    return _load_data()


def reset_portfolio(initial_balance: float = 10000.0) -> dict:
    """Reset portfolio to initial state"""
    data = {
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
    _save_data(data)
    return data


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
    data = _load_data()

    # Calculate position size
    position_value = data["balance"] * (position_size_percent / 100)
    margin_used = position_value
    position_size = (position_value * leverage) / entry_price

    position = {
        "id": len(data["history"]) + len(data["positions"]) + 1,
        "symbol": symbol,
        "direction": direction,
        "entry_price": entry_price,
        "current_price": entry_price,
        "leverage": leverage,
        "position_size": position_size,
        "margin_used": margin_used,
        "take_profit_price": take_profit_price,
        "stop_loss_price": stop_loss_price,
        "confidence": confidence,
        "reasoning": reasoning,
        "opened_at": datetime.utcnow().isoformat(),
        "unrealized_pnl": 0.0,
        "unrealized_pnl_percent": 0.0
    }

    data["balance"] -= margin_used
    data["positions"].append(position)
    _save_data(data)

    return position


def update_positions(current_prices: dict) -> list:
    """Update all positions with current prices and check for TP/SL"""
    data = _load_data()
    closed_positions = []

    for position in data["positions"][:]:  # Copy list to allow modification
        symbol = position["symbol"]
        if symbol not in current_prices:
            continue

        current_price = current_prices[symbol].get("price", position["entry_price"])
        position["current_price"] = current_price

        # Calculate PnL
        if position["direction"] == "long":
            price_change_percent = ((current_price - position["entry_price"]) / position["entry_price"]) * 100
        else:  # short
            price_change_percent = ((position["entry_price"] - current_price) / position["entry_price"]) * 100

        leveraged_pnl_percent = price_change_percent * position["leverage"]
        position["unrealized_pnl_percent"] = leveraged_pnl_percent
        position["unrealized_pnl"] = position["margin_used"] * (leveraged_pnl_percent / 100)

        # Check take profit / stop loss
        should_close = False
        close_reason = ""

        if position["direction"] == "long":
            if current_price >= position["take_profit_price"]:
                should_close = True
                close_reason = "take_profit"
            elif current_price <= position["stop_loss_price"]:
                should_close = True
                close_reason = "stop_loss"
        else:  # short
            if current_price <= position["take_profit_price"]:
                should_close = True
                close_reason = "take_profit"
            elif current_price >= position["stop_loss_price"]:
                should_close = True
                close_reason = "stop_loss"

        if should_close:
            closed = close_position(position["id"], current_price, close_reason)
            if closed:
                closed_positions.append(closed)
                # Reload data after close
                data = _load_data()

    _save_data(data)
    return closed_positions


def close_position(position_id: int, close_price: float, reason: str = "manual") -> Optional[dict]:
    """Close a position and record in history"""
    data = _load_data()

    position = None
    for p in data["positions"]:
        if p["id"] == position_id:
            position = p
            break

    if not position:
        return None

    # Calculate final PnL
    if position["direction"] == "long":
        price_change_percent = ((close_price - position["entry_price"]) / position["entry_price"]) * 100
    else:
        price_change_percent = ((position["entry_price"] - close_price) / position["entry_price"]) * 100

    leveraged_pnl_percent = price_change_percent * position["leverage"]
    realized_pnl = position["margin_used"] * (leveraged_pnl_percent / 100)

    # Create history record
    history_record = {
        **position,
        "close_price": close_price,
        "close_reason": reason,
        "closed_at": datetime.utcnow().isoformat(),
        "realized_pnl": realized_pnl,
        "realized_pnl_percent": leveraged_pnl_percent,
        "was_profitable": realized_pnl > 0,
        "hit_target": reason == "take_profit" and realized_pnl > 0
    }

    # Update portfolio
    data["balance"] += position["margin_used"] + realized_pnl
    data["positions"].remove(position)
    data["history"].append(history_record)

    # Update stats
    data["stats"]["total_trades"] += 1
    data["stats"]["total_pnl"] += realized_pnl
    if realized_pnl > 0:
        data["stats"]["winning_trades"] += 1
    else:
        data["stats"]["losing_trades"] += 1

    _save_data(data)
    return history_record


def get_performance_stats() -> dict:
    """Get overall performance statistics"""
    data = _load_data()
    stats = data["stats"]

    win_rate = 0
    if stats["total_trades"] > 0:
        win_rate = (stats["winning_trades"] / stats["total_trades"]) * 100

    total_return = ((data["balance"] - data["initial_balance"]) / data["initial_balance"]) * 100

    return {
        "current_balance": data["balance"],
        "initial_balance": data["initial_balance"],
        "total_return_percent": total_return,
        "total_pnl": stats["total_pnl"],
        "total_trades": stats["total_trades"],
        "winning_trades": stats["winning_trades"],
        "losing_trades": stats["losing_trades"],
        "win_rate": win_rate,
        "open_positions": len(data["positions"]),
        "history_count": len(data["history"])
    }


def get_performance_context(limit: int = 10) -> dict:
    """
    Summarise recent closed-trade outcomes for the advisory agent feedback loop.
    Returns a structured dict the advisory prompt can reason about.
    """
    data = _load_data()
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
        data = _load_data()
        existing = [p for p in data["positions"] if p["symbol"] == symbol]
        if existing:
            continue  # Skip if already have position

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
