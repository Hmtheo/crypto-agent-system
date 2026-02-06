// Crypto Agent Trading System - Frontend JavaScript

// Utility functions
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

function log(message, type = 'info') {
    const logContent = document.getElementById('logContent');
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `
        <span class="log-time">${new Date().toLocaleTimeString()}</span>
        <span class="log-message ${type}">${message}</span>
    `;
    logContent.insertBefore(entry, logContent.firstChild);
}

// API calls
async function fetchAPI(endpoint, options = {}) {
    try {
        const response = await fetch(`/api${endpoint}`, options);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        log(`Error: ${error.message}`, 'error');
        throw error;
    }
}

// Update price display
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

// Update portfolio display
function updatePortfolio(portfolio, stats) {
    if (stats) {
        document.getElementById('balance').textContent = formatCurrency(stats.current_balance);

        const pnlEl = document.getElementById('totalPnl');
        pnlEl.textContent = formatCurrency(stats.total_pnl);
        pnlEl.className = `stat-value ${stats.total_pnl >= 0 ? 'positive' : 'negative'}`;

        document.getElementById('winRate').textContent = `${stats.win_rate.toFixed(1)}%`;
        document.getElementById('totalTrades').textContent = stats.total_trades;
    }

    // Update positions
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
                        <th>P&L</th>
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

    // Update history
    const historyContent = document.getElementById('historyContent');
    if (portfolio && portfolio.history && portfolio.history.length > 0) {
        historyContent.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Direction</th>
                        <th>Entry</th>
                        <th>Exit</th>
                        <th>P&L</th>
                        <th>Result</th>
                        <th>Closed</th>
                    </tr>
                </thead>
                <tbody>
                    ${portfolio.history.slice().reverse().map(trade => `
                        <tr>
                            <td><strong>${trade.symbol}</strong></td>
                            <td>${trade.direction.toUpperCase()}</td>
                            <td>${formatCurrency(trade.entry_price)}</td>
                            <td>${formatCurrency(trade.close_price)}</td>
                            <td class="${trade.realized_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}">
                                ${formatCurrency(trade.realized_pnl)}
                            </td>
                            <td>${trade.was_profitable ? '✅ Win' : '❌ Loss'}</td>
                            <td>${formatTime(trade.closed_at)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        historyContent.innerHTML = '<p class="no-history">No trade history</p>';
    }
}

// Update analysis display
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

// Update recommendations display
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

    // Show overall advice
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

// Run all agents
async function runAgents() {
    const btn = document.getElementById('runAgents');
    btn.disabled = true;
    btn.textContent = '⏳ Running...';
    log('Starting all agents...', 'info');

    try {
        const result = await fetchAPI('/execute', { method: 'POST' });

        updatePrices(result.monitor?.prices);
        updateAnalysis(result.analysis);
        updateRecommendations(result.recommendations);

        // Fetch and update portfolio
        const stats = await fetchAPI('/portfolio/stats');
        updatePortfolio(result.portfolio, stats);

        document.getElementById('lastUpdate').textContent = `Last updated: ${new Date().toLocaleTimeString()}`;

        // Log results
        log('Monitor agent completed - prices fetched', 'success');
        log('Analysis agent completed - market analyzed', 'success');
        log('Advisory agent completed - recommendations generated', 'success');

        if (result.opened_positions?.length > 0) {
            result.opened_positions.forEach(pos => {
                log(`Opened ${pos.direction.toUpperCase()} position for ${pos.symbol} at ${formatCurrency(pos.entry_price)}`, 'success');
            });
        }

        if (result.closed_positions?.length > 0) {
            result.closed_positions.forEach(pos => {
                const outcome = pos.realized_pnl >= 0 ? 'profit' : 'loss';
                log(`Closed ${pos.symbol} position with ${formatCurrency(pos.realized_pnl)} ${outcome}`, pos.realized_pnl >= 0 ? 'success' : 'error');
            });
        }

    } catch (error) {
        log(`Failed to run agents: ${error.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '▶️ Run All Agents';
    }
}

// Update positions
async function updatePositions() {
    const btn = document.getElementById('updatePositions');
    btn.disabled = true;
    log('Updating positions...', 'info');

    try {
        const result = await fetchAPI('/portfolio/update', { method: 'POST' });
        const stats = await fetchAPI('/portfolio/stats');

        updatePortfolio(result.portfolio, stats);

        if (result.closed_positions?.length > 0) {
            result.closed_positions.forEach(pos => {
                const outcome = pos.realized_pnl >= 0 ? 'profit' : 'loss';
                log(`Position closed: ${pos.symbol} with ${formatCurrency(pos.realized_pnl)} ${outcome}`, pos.realized_pnl >= 0 ? 'success' : 'error');
            });
        } else {
            log('Positions updated - no closes triggered', 'info');
        }

    } catch (error) {
        log(`Failed to update positions: ${error.message}`, 'error');
    } finally {
        btn.disabled = false;
    }
}

// Reset portfolio
async function resetPortfolio() {
    if (!confirm('Are you sure you want to reset your portfolio? All positions and history will be lost.')) {
        return;
    }

    log('Resetting portfolio...', 'info');

    try {
        await fetchAPI('/portfolio/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ initial_balance: 10000 })
        });

        const portfolio = await fetchAPI('/portfolio');
        const stats = await fetchAPI('/portfolio/stats');
        updatePortfolio(portfolio, stats);

        log('Portfolio reset to $10,000', 'success');

    } catch (error) {
        log(`Failed to reset portfolio: ${error.message}`, 'error');
    }
}

// Load initial prices
async function loadPrices() {
    try {
        const prices = await fetchAPI('/prices');
        updatePrices(prices);
    } catch (error) {
        console.error('Failed to load prices:', error);
    }
}

// Load portfolio
async function loadPortfolio() {
    try {
        const portfolio = await fetchAPI('/portfolio');
        const stats = await fetchAPI('/portfolio/stats');
        updatePortfolio(portfolio, stats);
    } catch (error) {
        console.error('Failed to load portfolio:', error);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Load initial data
    loadPrices();
    loadPortfolio();

    // Set up event listeners
    document.getElementById('runAgents').addEventListener('click', runAgents);
    document.getElementById('updatePositions').addEventListener('click', updatePositions);
    document.getElementById('resetPortfolio').addEventListener('click', resetPortfolio);

    // Auto-refresh prices every 30 seconds
    setInterval(loadPrices, 30000);

    log('System initialized', 'success');
});
