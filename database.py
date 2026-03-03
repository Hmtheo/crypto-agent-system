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
    Create tables if they do not exist. Safe to call on every startup.
    Includes migration steps to add user_id columns to existing tables.
    """
    with get_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         SERIAL PRIMARY KEY,
                google_id  VARCHAR(255) UNIQUE NOT NULL,
                email      VARCHAR(255) UNIQUE NOT NULL,
                name       VARCHAR(255),
                picture    TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS portfolio (
                id              SERIAL PRIMARY KEY,
                user_id         INTEGER REFERENCES users(id),
                balance         DOUBLE PRECISION NOT NULL DEFAULT 10000.0,
                initial_balance DOUBLE PRECISION NOT NULL DEFAULT 10000.0,
                total_trades    INTEGER          NOT NULL DEFAULT 0,
                winning_trades  INTEGER          NOT NULL DEFAULT 0,
                losing_trades   INTEGER          NOT NULL DEFAULT 0,
                total_pnl       DOUBLE PRECISION NOT NULL DEFAULT 0.0
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id                     SERIAL           PRIMARY KEY,
                user_id                INTEGER          REFERENCES users(id),
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
                user_id                INTEGER          REFERENCES users(id),
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

    # Migration for existing deployments — each runs in its own transaction
    # so a failure in one doesn't block the others.
    migrations = [
        # Drop old singleton constraint (only present in pre-auth deployments)
        "ALTER TABLE portfolio DROP CONSTRAINT IF EXISTS portfolio_id_check",
        # Add user_id columns if upgrading from pre-auth schema
        "ALTER TABLE portfolio     ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
        "ALTER TABLE positions     ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
        "ALTER TABLE trade_history ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    ]
    for sql in migrations:
        try:
            with get_cursor() as cur:
                cur.execute(sql)
        except Exception:
            pass  # benign — column/constraint already in desired state


def get_or_create_user(google_id: str, email: str, name: str, picture: str) -> int:
    """
    Upsert a user record by Google ID and return the internal user id.
    """
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO users (google_id, email, name, picture)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (google_id) DO UPDATE
                SET email   = EXCLUDED.email,
                    name    = EXCLUDED.name,
                    picture = EXCLUDED.picture
            RETURNING id
        """, (google_id, email, name, picture))
        return cur.fetchone()["id"]


def get_user_portfolio_id(user_id: int) -> int:
    """
    Return the portfolio id for a user, creating one if it doesn't exist.
    """
    with get_cursor() as cur:
        cur.execute("SELECT id FROM portfolio WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        if row:
            return row["id"]

        cur.execute("""
            INSERT INTO portfolio
                (user_id, balance, initial_balance,
                 total_trades, winning_trades, losing_trades, total_pnl)
            VALUES (%s, 10000.0, 10000.0, 0, 0, 0, 0.0)
            RETURNING id
        """, (user_id,))
        return cur.fetchone()["id"]
