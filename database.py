"""
database.py - PostgreSQL connection and schema initialization
"""
import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager


def get_connection():
    """Return a new psycopg2 connection using DATABASE_URL from environment."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    # Railway provides postgres:// URLs; psycopg2 requires postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(database_url)


@contextmanager
def get_cursor():
    """
    Context manager that yields a RealDictCursor and handles
    commit/rollback + connection close automatically.

    Usage:
        with get_cursor() as cur:
            cur.execute(...)
            rows = cur.fetchall()
    """
    conn = get_connection()
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                yield cur
    finally:
        conn.close()


def init_db():
    """
    Create tables if they do not exist, then seed the portfolio row
    with default values if it is empty. Safe to call on every startup.
    """
    with get_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS portfolio (
                id              INTEGER PRIMARY KEY DEFAULT 1,
                balance         DOUBLE PRECISION NOT NULL DEFAULT 10000.0,
                initial_balance DOUBLE PRECISION NOT NULL DEFAULT 10000.0,
                total_trades    INTEGER          NOT NULL DEFAULT 0,
                winning_trades  INTEGER          NOT NULL DEFAULT 0,
                losing_trades   INTEGER          NOT NULL DEFAULT 0,
                total_pnl       DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                CHECK (id = 1)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id                     SERIAL           PRIMARY KEY,
                symbol                 VARCHAR(20)      NOT NULL,
                direction              VARCHAR(10)      NOT NULL,
                entry_price            DOUBLE PRECISION NOT NULL,
                current_price          DOUBLE PRECISION NOT NULL,
                leverage               INTEGER          NOT NULL,
                position_size          DOUBLE PRECISION NOT NULL,
                margin_used            DOUBLE PRECISION NOT NULL,
                take_profit_price      DOUBLE PRECISION NOT NULL,
                stop_loss_price        DOUBLE PRECISION NOT NULL,
                confidence             INTEGER          NOT NULL,
                reasoning              TEXT             NOT NULL,
                opened_at              TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
                unrealized_pnl         DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                unrealized_pnl_percent DOUBLE PRECISION NOT NULL DEFAULT 0.0
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS trade_history (
                id                     INTEGER          NOT NULL,
                symbol                 VARCHAR(20)      NOT NULL,
                direction              VARCHAR(10)      NOT NULL,
                entry_price            DOUBLE PRECISION NOT NULL,
                close_price            DOUBLE PRECISION NOT NULL,
                current_price          DOUBLE PRECISION NOT NULL,
                leverage               INTEGER          NOT NULL,
                position_size          DOUBLE PRECISION NOT NULL,
                margin_used            DOUBLE PRECISION NOT NULL,
                take_profit_price      DOUBLE PRECISION NOT NULL,
                stop_loss_price        DOUBLE PRECISION NOT NULL,
                confidence             INTEGER          NOT NULL,
                reasoning              TEXT             NOT NULL,
                opened_at              TIMESTAMPTZ      NOT NULL,
                closed_at              TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
                unrealized_pnl         DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                unrealized_pnl_percent DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                realized_pnl           DOUBLE PRECISION NOT NULL,
                realized_pnl_percent   DOUBLE PRECISION NOT NULL,
                close_reason           VARCHAR(50)      NOT NULL,
                was_profitable         BOOLEAN          NOT NULL,
                hit_target             BOOLEAN          NOT NULL
            )
        """)

        # Seed the single portfolio row if it does not yet exist
        cur.execute("""
            INSERT INTO portfolio (id, balance, initial_balance,
                                   total_trades, winning_trades, losing_trades, total_pnl)
            SELECT 1, 10000.0, 10000.0, 0, 0, 0, 0.0
            WHERE NOT EXISTS (SELECT 1 FROM portfolio WHERE id = 1)
        """)
