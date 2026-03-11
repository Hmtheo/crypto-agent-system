// Crypto Agent Trading System - Frontend JavaScript

// =====================
// State
// =====================

let currentView = 'dashboard';
let activityLogs = [];  // structured activity log for Logs view
let portfolioHistory = [];  // latest trade history for Logs view

// =====================
// Utility functions
// =====================

function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(amount);
}

function formatPercent(value) {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(2)}%`;
}

function formatTime(isoString) {
    return new Date(isoString).toLocaleString();
}

function formatTokens(tokens) {
    if (!tokens) return null;
    if (typeof tokens === 'number') return tokens.toLocaleString();
    if (tokens.total) return tokens.total.toLocaleString();
    if (tokens.input_tokens != null) {
        const total = (tokens.input_tokens || 0) + (tokens.output_tokens || 0);
        return total.toLocaleString();
    }
    return null;
}

// =====================
// Activity log (in-memory structured log)
// =====================

function addActivityEntry({ action, agent = null, status = 'info', details = '', tokens = null }) {
    activityLogs.unshift({
        time: new Date(),
        action,
        agent,
        status,
        details,
        tokens
    });
    // Keep last 200 entries
    if (activityLogs.length > 200) activityLogs.length = 200;
    // If logs view is active, refresh it
    if (currentView === 'logs') renderLogsView();
}

// =====================
// Navigation
// =====================

function navigateTo(view) {
    currentView = view;

    document.getElementById('dashboardView').style.display = view === 'dashboard' ? '' : 'none';
    document.getElementById('logsView').style.display = view === 'logs' ? '' : 'none';

    document.querySelectorAll('.nav-item[data-view]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === view);
    });

    if (view === 'logs') renderLogsView();
}

// =====================
// Render Logs View
// =====================

function renderLogsView() {
    renderTransactionHistory();
    renderActivityLogTable();
}

function renderTransactionHistory() {
    const el = document.getElementById('logsHistoryContent');
    if (!portfolioHistory || portfolioHistory.length === 0) {
        el.innerHTML = '<p class="no-data-msg">No closed trades yet.</p>';
        return;
    }

    const rows = portfolioHistory.slice().reverse().map(trade => `
        <tr>
            <td><strong>${trade.symbol}</strong></td>
            <td class="${trade.direction === 'long' ? 'pnl-positive' : 'pnl-negative'}">${trade.direction.toUpperCase()}</td>
            <td>${formatCurrency(trade.entry_price)}</td>
            <td>${formatCurrency(trade.close_price)}</td>
            <td>${trade.leverage != null ? trade.leverage + 'x' : '—'}</td>
            <td class="${trade.realized_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}">
                ${formatCurrency(trade.realized_pnl)}
            </td>
            <td class="${trade.realized_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}">
                ${trade.realized_pnl_percent != null ? formatPercent(trade.realized_pnl_percent) : '—'}
            </td>
            <td>${trade.close_reason || '—'}</td>
            <td>${trade.was_profitable ? '<span class="activity-badge success">Win</span>' : '<span class="activity-badge error">Loss</span>'}</td>
            <td style="white-space:nowrap;">${formatTime(trade.closed_at)}</td>
        </tr>
    `).join('');

    el.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Direction</th>
                    <th>Entry Price</th>
                    <th>Exit Price</th>
                    <th>Leverage</th>
                    <th>Realized P&amp;L</th>
                    <th>P&amp;L %</th>
                    <th>Close Reason</th>
                    <th>Result</th>
                    <th>Closed At</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    `;
}

function renderActivityLogTable() {
    const el = document.getElementById('logsActivityContent');
    if (activityLogs.length === 0) {
        el.innerHTML = '<p class="no-data-msg">No activity yet. Run agents to get started.</p>';
        return;
    }

    const rows = activityLogs.map(entry => {
        const tokenStr = formatTokens(entry.tokens);
        const tokenCell = tokenStr
            ? `<span class="tokens-cell">${tokenStr}</span>`
            : `<span class="tokens-na">—</span>`;

        const badgeClass = entry.status === 'success' ? 'success'
            : entry.status === 'error' ? 'error' : 'info';

        return `
            <tr>
                <td style="white-space:nowrap;">${entry.time.toLocaleTimeString()}</td>
                <td>${entry.action}</td>
                <td>${entry.agent || '—'}</td>
                <td><span class="activity-badge ${badgeClass}">${entry.status}</span></td>
                <td>${entry.details}</td>
                <td>${tokenCell}</td>
            </tr>
        `;
    }).join('');

    el.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Action</th>
                    <th>Agent</th>
                    <th>Status</th>
                    <th>Details</th>
                    <th>Tokens Used</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    `;
}

// =====================
// API calls
// =====================

async function fetchAPI(endpoint, options = {}) {
    try {
        const response = await fetch(`/api${endpoint}`, options);
        if (response.status === 401) {
            window.location.href = '/login';
            return;
        }
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        addActivityEntry({ action: 'API Error', status: 'error', details: error.message });
        throw error;
    }
}

// =====================
// Headlines / news
// =====================

let headlinesExpanded = false;

async function loadHeadlines() {
    try {
        const result = await fetchAPI('/news');
        updateHeadlines(result.news || []);
    } catch (error) {
        console.error('Failed to load headlines:', error);
    }
}

function updateHeadlines(articles) {
    const track = document.getElementById('headlinesTrack');
    const cards = document.getElementById('headlinesCards');
    if (!articles || articles.length === 0) {
        track.innerHTML = '<span class="headlines-loading">No news available</span>';
        return;
    }

    const tickerItems = articles.map(a => `
        <span class="ticker-item">
            <a href="${a.url || '#'}" target="_blank" rel="noopener">${a.title}</a>
            <span class="ticker-source">${a.source}</span>
            <span class="ticker-time">${a.published_at}</span>
        </span>
    `).join('');
    track.innerHTML = tickerItems + tickerItems;

    cards.innerHTML = articles.map(a => `
        <div class="headline-card">
            <a href="${a.url || '#'}" target="_blank" rel="noopener">${a.title}</a>
            <div class="headline-card-meta">${a.source} &middot; ${a.published_at}</div>
            ${a.body_snippet ? `<div class="headline-card-snippet">${a.body_snippet}</div>` : ''}
        </div>
    `).join('');
}

function toggleHeadlines() {
    headlinesExpanded = !headlinesExpanded;
    const cards = document.getElementById('headlinesCards');
    const btn = document.getElementById('toggleHeadlines');
    cards.style.display = headlinesExpanded ? 'grid' : 'none';
    btn.textContent = headlinesExpanded ? 'Hide articles \u25B4' : 'Show articles \u25BE';
}

// =====================
// Prices
// =====================

function updatePrices(prices) {
    if (!prices) return;

    const coins = {
        'BTC': { priceEl: 'btcPrice', changeEl: 'btcChange' },
        'ETH': { priceEl: 'ethPrice', changeEl: 'ethChange' },
        'SOL': { priceEl: 'solPrice', changeEl: 'solChange' }
    };

    for (const [symbol, elements] of Object.entries(coins)) {
        if (prices[symbol]) {
            const priceEl = document.getElementById(elements.priceEl);
            const changeEl = document.getElementById(elements.changeEl);

            priceEl.textContent = formatCurrency(prices[symbol].price);

            const change = prices[symbol].change_24h;
            changeEl.textContent = formatPercent(change);
            changeEl.className = `change ${change >= 0 ? 'positive' : 'negative'}`;
        }
    }
}

// =====================
// Portfolio
// =====================

function updatePortfolio(portfolio, stats) {
    if (stats) {
        document.getElementById('balance').textContent = formatCurrency(stats.current_balance);

        const pnlEl = document.getElementById('totalPnl');
        pnlEl.textContent = formatCurrency(stats.total_pnl);
        pnlEl.className = `stat-value ${stats.total_pnl >= 0 ? 'positive' : 'negative'}`;

        document.getElementById('winRate').textContent = `${stats.win_rate.toFixed(1)}%`;
        document.getElementById('totalTrades').textContent = stats.total_trades;
    }

    // Open positions
    const positionsContent = document.getElementById('positionsContent');
    if (portfolio && portfolio.positions && portfolio.positions.length > 0) {
        positionsContent.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Direction</th>
                        <th>Entry</th>
                        <th>Current</th>
                        <th>Leverage</th>
                        <th>P&amp;L</th>
                        <th>TP / SL</th>
                    </tr>
                </thead>
                <tbody>
                    ${portfolio.positions.map(pos => `
                        <tr>
                            <td><strong>${pos.symbol}</strong></td>
                            <td class="${pos.direction === 'long' ? 'pnl-positive' : 'pnl-negative'}">${pos.direction.toUpperCase()}</td>
                            <td>${formatCurrency(pos.entry_price)}</td>
                            <td>${formatCurrency(pos.current_price)}</td>
                            <td>${pos.leverage}x</td>
                            <td class="${pos.unrealized_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}">
                                ${formatCurrency(pos.unrealized_pnl)} (${formatPercent(pos.unrealized_pnl_percent)})
                            </td>
                            <td>${formatCurrency(pos.take_profit_price)} / ${formatCurrency(pos.stop_loss_price)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        positionsContent.innerHTML = '<p class="no-positions">No open positions</p>';
    }

    // Store history for Logs view
    if (portfolio && portfolio.history) {
        portfolioHistory = portfolio.history;
        if (currentView === 'logs') renderTransactionHistory();
    }
}

// =====================
// Analysis
// =====================

function updateAnalysis(analysis) {
    if (!analysis) return;

    document.getElementById('analysisLoading').style.display = 'none';
    document.getElementById('analysisContent').style.display = 'grid';

    const sentimentEl = document.getElementById('sentiment');
    sentimentEl.textContent = analysis.market_sentiment || 'Unknown';
    sentimentEl.className = `sentiment ${analysis.market_sentiment}`;

    document.getElementById('sentimentScore').textContent = `Score: ${analysis.sentiment_score || 0}`;
    document.getElementById('marketSummary').textContent = analysis.market_summary || 'No summary available';

    const riskEl = document.getElementById('riskLevel');
    riskEl.textContent = analysis.risk_level || 'Unknown';
    riskEl.className = `risk ${analysis.risk_level}`;
}

// =====================
// Recommendations
// =====================

function updateRecommendations(recommendations) {
    if (!recommendations || !recommendations.recommendations) return;

    document.getElementById('recommendationsLoading').style.display = 'none';
    const content = document.getElementById('recommendationsContent');
    content.style.display = 'grid';

    content.innerHTML = recommendations.recommendations.map(rec => `
        <div class="recommendation-card ${rec.action}">
            <h3>
                ${rec.symbol}
                <span class="action-badge ${rec.action}">${rec.action.toUpperCase()}</span>
            </h3>
            ${rec.action !== 'wait' ? `
                <div class="recommendation-details">
                    <div><span>Confidence:</span> <strong>${rec.confidence}%</strong></div>
                    <div><span>Leverage:</span> <strong>${rec.leverage}x</strong></div>
                    <div><span>Entry:</span> <strong>${formatCurrency(rec.entry_price)}</strong></div>
                    <div><span>Take Profit:</span> <strong>${formatCurrency(rec.take_profit_price)}</strong></div>
                    <div><span>Stop Loss:</span> <strong>${formatCurrency(rec.stop_loss_price)}</strong></div>
                    <div><span>Risk/Reward:</span> <strong>${rec.risk_reward_ratio?.toFixed(2) || 'N/A'}</strong></div>
                </div>
            ` : ''}
            <div class="reasoning">${rec.reasoning}</div>
        </div>
    `).join('');

    if (recommendations.portfolio_advice) {
        content.innerHTML += `
            <div class="recommendation-card" style="grid-column: 1 / -1; border-left-color: #00d4ff;">
                <h3>
                    Portfolio Advice
                    <span class="action-badge" style="background: rgba(0, 212, 255, 0.2); color: #00d4ff;">
                        ${recommendations.overall_market_stance?.toUpperCase() || 'N/A'}
                    </span>
                </h3>
                <div class="reasoning">${recommendations.portfolio_advice}</div>
            </div>
        `;
    }
}

// =====================
// Run All Agents
// =====================

async function runAgents() {
    const btn = document.getElementById('runAgents');
    btn.disabled = true;
    btn.textContent = 'Running...';

    addActivityEntry({ action: 'Run All Agents', agent: 'System', status: 'info', details: 'Starting monitor, analysis & advisory agents...' });

    try {
        const result = await fetchAPI('/execute', { method: 'POST' });

        updatePrices(result.monitor?.prices);
        updateAnalysis(result.analysis);
        updateRecommendations(result.recommendations);

        const stats = await fetchAPI('/portfolio/stats');
        updatePortfolio(result.portfolio, stats);

        document.getElementById('lastUpdate').textContent = `Updated ${new Date().toLocaleTimeString()}`;

        // Extract token usage if available
        const analysisTokens = result.analysis?.usage || result.analysis?.tokens_used || null;
        const advisoryTokens = result.recommendations?.usage || result.recommendations?.tokens_used || null;

        addActivityEntry({
            action: 'Run All Agents',
            agent: 'Monitor',
            status: 'success',
            details: 'Prices & news fetched',
            tokens: null
        });

        addActivityEntry({
            action: 'Run All Agents',
            agent: 'Analysis',
            status: 'success',
            details: `Sentiment: ${result.analysis?.market_sentiment || 'N/A'} | Risk: ${result.analysis?.risk_level || 'N/A'}`,
            tokens: analysisTokens
        });

        addActivityEntry({
            action: 'Run All Agents',
            agent: 'Advisory',
            status: 'success',
            details: `${result.recommendations?.recommendations?.length || 0} recommendations generated`,
            tokens: advisoryTokens
        });

        if (result.opened_positions?.length > 0) {
            result.opened_positions.forEach(pos => {
                addActivityEntry({
                    action: 'Trade Opened',
                    agent: 'Advisory',
                    status: 'success',
                    details: `${pos.direction.toUpperCase()} ${pos.symbol} at ${formatCurrency(pos.entry_price)}`
                });
            });
        }

        if (result.closed_positions?.length > 0) {
            result.closed_positions.forEach(pos => {
                addActivityEntry({
                    action: 'Position Closed',
                    agent: 'System',
                    status: pos.realized_pnl >= 0 ? 'success' : 'error',
                    details: `${pos.symbol} closed with ${formatCurrency(pos.realized_pnl)}`
                });
            });
        }

    } catch (error) {
        addActivityEntry({ action: 'Run All Agents', agent: 'System', status: 'error', details: error.message });
    } finally {
        btn.disabled = false;
        btn.textContent = '\u25B6 Run All Agents';
    }
}

// =====================
// Update Positions
// =====================

async function updatePositions() {
    const btn = document.getElementById('updatePositions');
    btn.disabled = true;

    addActivityEntry({ action: 'Update Positions', agent: 'System', status: 'info', details: 'Checking TP/SL levels...' });

    try {
        const result = await fetchAPI('/portfolio/update', { method: 'POST' });
        const stats = await fetchAPI('/portfolio/stats');
        updatePortfolio(result.portfolio, stats);

        if (result.closed_positions?.length > 0) {
            result.closed_positions.forEach(pos => {
                addActivityEntry({
                    action: 'Position Closed',
                    agent: 'System',
                    status: pos.realized_pnl >= 0 ? 'success' : 'error',
                    details: `${pos.symbol} closed with ${formatCurrency(pos.realized_pnl)}`
                });
            });
        } else {
            addActivityEntry({ action: 'Update Positions', agent: 'System', status: 'success', details: 'No TP/SL levels triggered' });
        }

    } catch (error) {
        addActivityEntry({ action: 'Update Positions', agent: 'System', status: 'error', details: error.message });
    } finally {
        btn.disabled = false;
    }
}

// =====================
// Reset Portfolio
// =====================

async function resetPortfolio() {
    if (!confirm('Are you sure you want to reset your portfolio? All positions and history will be lost.')) {
        return;
    }

    addActivityEntry({ action: 'Reset Portfolio', agent: 'System', status: 'info', details: 'Resetting to $10,000...' });

    try {
        await fetchAPI('/portfolio/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ initial_balance: 10000 })
        });

        const portfolio = await fetchAPI('/portfolio');
        const stats = await fetchAPI('/portfolio/stats');
        updatePortfolio(portfolio, stats);

        portfolioHistory = [];
        addActivityEntry({ action: 'Reset Portfolio', agent: 'System', status: 'success', details: 'Portfolio reset to $10,000' });

    } catch (error) {
        addActivityEntry({ action: 'Reset Portfolio', agent: 'System', status: 'error', details: error.message });
    }
}

// =====================
// Load initial data
// =====================

async function loadPrices() {
    try {
        const prices = await fetchAPI('/prices');
        updatePrices(prices);
    } catch (error) {
        console.error('Failed to load prices:', error);
    }
}

async function loadPortfolio() {
    try {
        const portfolio = await fetchAPI('/portfolio');
        const stats = await fetchAPI('/portfolio/stats');
        updatePortfolio(portfolio, stats);
    } catch (error) {
        console.error('Failed to load portfolio:', error);
    }
}

// =====================
// Initialize
// =====================

document.addEventListener('DOMContentLoaded', () => {
    // Load initial data
    loadPrices();
    loadPortfolio();
    loadHeadlines();

    // Navigation
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => navigateTo(btn.dataset.view));
    });

    // Action buttons
    document.getElementById('runAgents').addEventListener('click', runAgents);
    document.getElementById('updatePositions').addEventListener('click', updatePositions);
    document.getElementById('resetPortfolio').addEventListener('click', resetPortfolio);

    // News
    document.getElementById('refreshNews').addEventListener('click', loadHeadlines);
    document.getElementById('toggleHeadlines').addEventListener('click', toggleHeadlines);

    // Auto-refresh
    setInterval(loadPrices, 30000);
    setInterval(loadHeadlines, 300000);

    addActivityEntry({ action: 'System Start', agent: 'System', status: 'success', details: 'Perple initialized' });
});
