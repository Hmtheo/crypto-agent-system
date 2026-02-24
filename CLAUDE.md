# CLAUDE.md

This file provides guidance for AI assistants (Claude and others) working in this repository.

## Project Overview

**Crypto Agent System** is an AI-powered cryptocurrency paper trading simulation. It combines:
- Real-time market data from CoinGecko (free, no API key)
- Claude AI analysis and trade recommendations
- A paper trading engine (no real money) with leverage, stop-loss, and take-profit
- A browser-based dashboard for monitoring and interaction

Supported coins: **Bitcoin (BTC)**, **Ethereum (ETH)**, **Solana (SOL)**

---

## Repository Structure

```
crypto-agent-system/
├── agents/
│   ├── __init__.py       # Module init (empty)
│   ├── monitor.py        # Fetches market data from CoinGecko
│   ├── analysis.py       # Claude-powered market sentiment analysis
│   └── advisory.py       # Claude-powered trade recommendations
├── static/
│   ├── index.html        # Single-page dashboard
│   ├── app.js            # Frontend logic (vanilla JS)
│   └── styles.css        # Dark-theme stylesheet
├── .github/
│   ├── workflows/
│   │   └── codeql-analysis.yml   # Security scanning
│   └── dependabot.yml            # Dependency updates
├── main.py               # FastAPI application + all API endpoints
├── paper_trading.py      # Simulated trading engine
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variable template
└── .gitignore
```

---

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend framework | FastAPI | 0.109.0 |
| ASGI server | Uvicorn | 0.27.0 |
| HTTP client | httpx (async) | 0.26.0 |
| AI | Anthropic Claude API | 0.18.1 |
| Config | python-dotenv | 1.0.0 |
| Validation | Pydantic | 2.5.3 |
| Frontend | Vanilla HTML/CSS/JS | — |
| Charts | Chart.js | CDN |
| Data persistence | JSON files | — |
| CI/CD | GitHub Actions CodeQL | — |

---

## Setup & Running

### Prerequisites

- Python 3.x
- An Anthropic API key

### Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd crypto-agent-system

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Running the Server

```bash
python main.py
# or with auto-reload for development:
uvicorn main:app --reload
```

The app will be available at `http://localhost:8000`.

---

## API Endpoints

All endpoints are defined in `main.py`. The base URL is `http://localhost:8000`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves the dashboard (index.html) |
| GET | `/api/health` | Health check |
| GET | `/api/prices` | Current BTC/ETH/SOL prices |
| GET | `/api/history/{coin_id}` | Historical price data for chart |
| POST | `/api/monitor` | Run the monitor agent |
| POST | `/api/analyze` | Run monitor + analysis agents |
| POST | `/api/recommend` | Run all agents, return recommendations |
| GET | `/api/portfolio` | Current portfolio state |
| POST | `/api/portfolio/reset` | Reset portfolio to initial balance |
| GET | `/api/portfolio/stats` | Performance stats (win rate, return) |
| POST | `/api/portfolio/update` | Update positions, check TP/SL triggers |
| POST | `/api/portfolio/close` | Manually close a position |
| POST | `/api/execute` | Full pipeline: agents + auto-execute trades |

---

## Agent Architecture

The three agents in `agents/` form a pipeline:

```
monitor.py  →  analysis.py  →  advisory.py
(market data)  (sentiment AI)  (trade recs AI)
```

### `agents/monitor.py`
- Fetches prices, 24h change, volume, and market cap from CoinGecko's public API
- Retrieves global market data (total cap, BTC/ETH dominance)
- Gets trending coins from CoinGecko's trending endpoint
- All functions are `async`; failures return error objects rather than raising

### `agents/analysis.py`
- Calls Claude (`claude-sonnet-4-20250514`) with monitor data as context
- Returns structured JSON:
  ```json
  {
    "sentiment": "bullish|bearish|neutral",
    "sentiment_score": -100..100,
    "coins": { "BTC": { "trend": "...", "strength": "...", "key_factors": [] }, ... },
    "market_summary": "...",
    "risk_level": "low|medium|high"
  }
  ```
- Handles Claude responses that wrap JSON in markdown code fences

### `agents/advisory.py`
- Calls Claude (`claude-sonnet-4-20250514`) with both monitor and analysis data
- Returns structured JSON with trade recommendations:
  ```json
  {
    "recommendations": [
      {
        "symbol": "BTC",
        "action": "long|short|hold",
        "confidence": 0..100,
        "leverage": 1..10,
        "entry_price": 0.0,
        "take_profit": 0.0,
        "stop_loss": 0.0,
        "reasoning": "...",
        "risk_reward": 0.0
      }
    ],
    "overall_stance": "...",
    "portfolio_advice": "..."
  }
  ```
- Leverage rules enforced in the prompt:
  - Confidence < 50 → 1–3x leverage
  - Confidence 50–75 → 4–6x leverage
  - Confidence > 75 → 7–10x leverage
  - Minimum risk/reward ratio: 1.5

---

## Paper Trading Engine (`paper_trading.py`)

Trades are persisted to `data/paper_trades.json` (auto-created).

### Key Concepts

- **Position**: long or short, with entry price, leverage, size, TP, SL
- **PnL**: `(price_delta / entry_price) * leverage * position_size` (long); negated for short
- **Auto-execution**: `auto_execute_recommendations()` opens positions from advisory output
- **TP/SL**: Checked on every `update_positions()` call

### Important Functions

| Function | Description |
|----------|-------------|
| `open_position(symbol, direction, entry_price, size, leverage, tp, sl)` | Open a new trade |
| `close_position(position_id, current_price)` | Close and record a trade |
| `update_positions(current_prices)` | Recalculate PnL; trigger TP/SL |
| `get_portfolio()` | Return full portfolio state dict |
| `reset_portfolio()` | Reset balance to $10,000, clear all positions |
| `get_performance_stats()` | Win rate, total return, open/closed trade counts |
| `auto_execute_recommendations(recommendations, prices)` | Open positions from advisor JSON |

---

## Frontend (`static/`)

The UI is a single HTML page with no frontend framework.

### `static/index.html`
Sections (in order):
1. Control panel — "Run All Agents", "Update Positions", "Reset Portfolio" buttons
2. Portfolio summary cards (balance, P&L, win rate, trade count)
3. Live price cards (BTC, ETH, SOL) with 24h change
4. AI analysis display (sentiment badge, market summary, risk level)
5. Trade recommendation cards
6. Open positions table
7. Trade history table
8. Activity log (timestamped events)

### `static/app.js`
Key functions:
- `fetchAPI(path, method, body)` — central HTTP helper
- `updatePrices(data)` — refresh price cards
- `updatePortfolio(data)` — refresh balance, positions, history tables
- `updateAnalysis(data)` — display sentiment/risk
- `updateRecommendations(data)` — render recommendation cards
- `runAgents()` — POST `/execute`, display all results
- `updatePositions()` — POST `/portfolio/update`
- `resetPortfolio()` — POST `/portfolio/reset` with confirm dialog
- Auto-refresh prices every **30 seconds**

### `static/styles.css`
- Dark theme, gradient backgrounds
- Color palette: cyan `#00d4ff` / purple `#7b2cbf` primary, green success, red error, yellow warning
- Coin border colors: BTC = orange, ETH = purple, SOL = green
- Responsive breakpoint at **768px**

---

## Key Conventions

### Python
- All I/O-bound functions are `async def`
- Type hints used throughout
- Pydantic `BaseModel` for request body validation in FastAPI routes
- `.env` loaded via `python-dotenv` at startup
- `try/except` around all external API calls; failures return structured error dicts
- No database — portfolio state lives in `data/paper_trades.json`

### JavaScript
- `async/await` for all API calls; errors logged to activity log
- Vanilla DOM manipulation — no React/Vue/etc.
- `camelCase` for all functions and variables
- Utility formatters: `formatCurrency()`, `formatPercent()`, `formatTime()`
- All activity is appended to the on-screen log with a timestamp

### Claude API Calls
- Model: `claude-sonnet-4-20250514` (used in both `analysis.py` and `advisory.py`)
- Responses must be valid JSON; both agents strip markdown code fences before parsing
- Prompts include explicit JSON schema examples to guide structured output
- Temperature not set (uses model default)

### Git / CI
- `main` is the protected branch; feature work goes on separate branches
- CodeQL runs on push and PRs targeting `main` (Python language)
- No linter or formatter is currently configured

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | API key for Claude (get from console.anthropic.com) |

Copy `.env.example` to `.env` and fill in the value. Never commit `.env`.

---

## Testing

There are **no automated tests** in this repository. When adding tests:
- Place them in a `tests/` directory
- Use `pytest` (not currently in `requirements.txt` — add it)
- Mock CoinGecko and Anthropic HTTP calls to avoid network dependency

---

## Common Development Tasks

### Add a new cryptocurrency
1. Add its CoinGecko ID to the `COINS` dict in `agents/monitor.py`
2. Add price handling in `main.py` and `paper_trading.py`
3. Add a price card and CSS border color in `static/index.html` and `static/styles.css`

### Change the AI model
Update the `model` parameter in both `agents/analysis.py` and `agents/advisory.py`.

### Modify leverage rules
Edit the leverage guidance section in the system prompt inside `agents/advisory.py`.

### Persist data differently
Replace the JSON file logic in `paper_trading.py` with a database client (e.g., SQLite via `aiosqlite`).

### Run with hot-reload
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## Security Notes

- The Anthropic API key must be kept secret — it is loaded from `.env` only
- CodeQL scans run automatically on all PRs; do not merge if critical issues are flagged
- CoinGecko requests use httpx with default TLS verification
- No authentication on the dashboard — do not expose port 8000 publicly without a reverse proxy
