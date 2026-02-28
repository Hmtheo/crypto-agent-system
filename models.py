"""
SQLAlchemy ORM models - User, Portfolio, Position, TradeHistory
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship
from database import Base


def _uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String)
    picture = Column(String)
    google_sub = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    portfolios = relationship("Portfolio", back_populates="user", cascade="all, delete-orphan")


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, default="Default Portfolio")
    balance = Column(Float, default=10000.0)
    initial_balance = Column(Float, default=10000.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="portfolios")
    positions = relationship("Position", back_populates="portfolio", cascade="all, delete-orphan")
    trade_history = relationship("TradeHistory", back_populates="portfolio", cascade="all, delete-orphan")


class Position(Base):
    __tablename__ = "positions"

    id = Column(String, primary_key=True, default=_uuid)
    portfolio_id = Column(String, ForeignKey("portfolios.id"), nullable=False, index=True)
    symbol = Column(String, nullable=False)
    direction = Column(String, nullable=False)  # "long" or "short"
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float)
    leverage = Column(Integer, default=1)
    position_size = Column(Float)
    margin_used = Column(Float)
    take_profit_price = Column(Float)
    stop_loss_price = Column(Float)
    confidence = Column(Integer)
    reasoning = Column(Text)
    opened_at = Column(DateTime, default=datetime.utcnow)
    unrealized_pnl = Column(Float, default=0.0)
    unrealized_pnl_percent = Column(Float, default=0.0)

    portfolio = relationship("Portfolio", back_populates="positions")


class TradeHistory(Base):
    __tablename__ = "trade_history"

    id = Column(String, primary_key=True, default=_uuid)
    portfolio_id = Column(String, ForeignKey("portfolios.id"), nullable=False, index=True)
    symbol = Column(String, nullable=False)
    direction = Column(String, nullable=False)
    entry_price = Column(Float, nullable=False)
    close_price = Column(Float)
    leverage = Column(Integer, default=1)
    position_size = Column(Float)
    margin_used = Column(Float)
    take_profit_price = Column(Float)
    stop_loss_price = Column(Float)
    confidence = Column(Integer)
    reasoning = Column(Text)
    opened_at = Column(DateTime)
    closed_at = Column(DateTime, default=datetime.utcnow)
    close_reason = Column(String)
    realized_pnl = Column(Float, default=0.0)
    realized_pnl_percent = Column(Float, default=0.0)
    was_profitable = Column(Boolean, default=False)
    hit_target = Column(Boolean, default=False)

    portfolio = relationship("Portfolio", back_populates="trade_history")
