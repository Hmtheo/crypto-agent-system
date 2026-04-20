/* =============================================
   Crypto Agent Dashboard — app.js
   All API endpoints unchanged from original.
   DOM IDs + structure updated for new HTML.
   ============================================= */

// =====================
// State
// =====================

let currentView = 'dashboard';
let activityLogs = [];
let portfolioHistory = [];
let pnlChart = null;

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
    return sign + value.toFixed(2) + '%';
}

function formatTime(isoString) {
    return new Date(isoString).toLocaleString();
}

function formatTokens(tokens) {
    if (!tokens) return null;
    if (typeof tokens === 'number') return tokens.toLocaleString();
    if (tokens.total) return tokens.total.toLocaleString();
    if (tokens.input_tokens != null) {
        var total = (tokens.input_tokens || 0) + (tokens.output_tokens || 0);
        return total.toLocaleString();
    }
    return null;
}

function timeAgo(isoString) {
    if (!isoString) return '';
    var diff = Date.now() - new Date(isoString).getTime();
    var mins = Math.floor(diff / 60000);
    if (mins < 60) return mins + ' min ago';
    var hrs = Math.floor(mins / 60);
    if (hrs < 24) return hrs + 'h ago';
    return Math.floor(hrs / 24) + 'd ago';
}

// =====================
// Activity log
// =====================

function addActivityEntry(opts) {
    activityLogs.unshift({
        time: new Date(),
        action: opts.action,
        agent: opts.agent || null,
        status: opts.status || 'info',
        details: opts.details || '',
        tokens: opts.tokens || null
    });
    if (activityLogs.length > 200) activityLogs.length = 200;
    if (currentView === 'logs') renderLogsView();
}

// =====================
// Navigation
// =====================

function navigateTo(view) {
    currentView = view;

    document.querySelectorAll('.view').forEach(function (el) {
        el.classList.remove('active');
    });

    var viewMap = {
        dashboard: 'dashboardView',
        news: 'newsView',
        logs: 'logsView'
    };
    var target = document.getElementById(viewMap[view]);
    if (target) target.classList.add('active');

    document.querySelectorAll('.nav-item').forEach(function (btn) {
        btn.classList.toggle('active', btn.dataset.view === view);
    });

    if (view === 'logs') renderLogsView();
}

// =====================
// API calls
// =====================

async function fetchAPI(endpoint, options) {
    options = options || {};
    try {
        var response = await fetch('/api' + endpoint, options);
        if (response.status === 401) {
            window.location.href = '/login';
            return;
        }
        if (!response.ok) {
            throw new Error('HTTP error! status: ' + response.status);
        }
        return await response.json();
    } catch (error) {
        addActivityEntry({ action: 'API Error', status: 'error', details: error.message });
        throw error;
    }
}

// =====================
// Prices
// =====================

function updatePrices(prices) {
    if (!prices) return;

    var coins = {
        BTC: { priceEl: 'btcPrice', changeEl: 'btcChange' },
        ETH: { priceEl: 'ethPrice', changeEl: 'ethChange' },
        SOL: { priceEl: 'solPrice', changeEl: 'solChange' }
    };

    for (var symbol in coins) {
        if (prices[symbol]) {
            var priceEl = document.getElementById(coins[symbol].priceEl);
            var changeEl = document.getElementById(coins[symbol].changeEl);

            priceEl.textContent = formatCurrency(prices[symbol].price);

            var change = prices[symbol].change_24h;
            changeEl.textContent = formatPercent(change);
            changeEl.className = 'ticker-change ' + (change >= 0 ? 'positive' : 'negative');
        }
    }
}

// =====================
// Portfolio
// =====================

function updatePortfolio(portfolio, stats) {
    if (stats) {
        document.getElementById('balance').textContent = formatCurrency(stats.current_balance);

        var pnlEl = document.getElementById('totalPnl');
        pnlEl.textContent = formatCurrency(stats.total_pnl);
        pnlEl.className = 'metric-value ' + (stats.total_pnl >= 0 ? 'positive' : 'negative');

        document.getElementById('winRate').textContent = stats.win_rate.toFixed(1) + '%';
        document.getElementById('totalTrades').textContent = stats.total_trades + ' trades';
    }

    // Open positions
    var posEl = document.getElementById('positionsContent');
    if (portfolio && portfolio.positions && portfolio.positions.length > 0) {
        document.getElementById('openPositionCount').textContent = portfolio.positions.length;
        posEl.innerHTML =
            '<table class="data-table">' +
            '<thead><tr>' +
            '<th>Symbol</th><th>Direction</th><th>Entry</th><th>Current</th><th>Lev.</th><th>P&L</th><th>TP / SL</th>' +
            '</tr></thead><tbody>' +
            portfolio.positions.map(function (pos) {
                return '<tr>' +
                    '<td class="sym">' + pos.symbol + '</td>' +
                    '<td class="' + (pos.direction === 'long' ? 'positive' : 'negative') + '">' + pos.direction + '</td>' +
                    '<td>' + formatCurrency(pos.entry_price) + '</td>' +
                    '<td>' + formatCurrency(pos.current_price) + '</td>' +
                    '<td>' + pos.leverage + 'x</td>' +
                    '<td class="' + (pos.unrealized_pnl >= 0 ? 'positive' : 'negative') + '">' +
                    formatCurrency(pos.unrealized_pnl) + ' (' + formatPercent(pos.unrealized_pnl_percent) + ')' +
                    '</td>' +
                    '<td>' + formatCurrency(pos.take_profit_price) + ' / ' + formatCurrency(pos.stop_loss_price) + '</td>' +
                    '</tr>';
            }).join('') +
            '</tbody></table>';
    } else {
        document.getElementById('openPositionCount').textContent = '0';
        posEl.innerHTML = '<p class="empty-state">No open positions</p>';
    }

    // Store history for logs view
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

    var section = document.getElementById('analysisSection');
    section.style.display = '';

    var sentimentEl = document.getElementById('sentiment');
    var sentiment = analysis.market_sentiment || 'unknown';
    sentimentEl.textContent = sentiment;
    sentimentEl.className = 'badge sentiment-' + sentiment;

    var riskEl = document.getElementById('riskLevel');
    var risk = analysis.risk_level || 'unknown';
    riskEl.textContent = risk;
    riskEl.className = 'badge risk-' + risk;

    document.getElementById('marketSummary').textContent = analysis.market_summary || '';
}

// =====================
// Recommendations
// =====================

function updateRecommendations(recommendations) {
    if (!recommendations || !recommendations.recommendations) return;

    document.getElementById('analysisLoading').style.display = 'none';
    var content = document.getElementById('recommendationsContent');
    content.style.display = 'grid';

    // Market stance badge
    if (recommendations.overall_market_stance) {
        var stanceEl = document.getElementById('marketStance');
        stanceEl.style.display = '';
        stanceEl.textContent = recommendations.overall_market_stance;
    }

    var html = recommendations.recommendations.map(function (rec) {
        var actionClass = rec.action === 'long' ? 'badge-success' :
            rec.action === 'short' ? 'badge-danger' : 'badge-info';

        var details = '';
        if (rec.action !== 'wait') {
            details =
                '<div class="signal-row"><span>Confidence</span><span class="signal-val">' + rec.confidence + '%</span></div>' +
                '<div class="signal-row"><span>Leverage</span><span class="signal-val">' + rec.leverage + 'x</span></div>' +
                '<div class="signal-row"><span>Entry</span><span class="signal-val">' + formatCurrency(rec.entry_price) + '</span></div>' +
                '<div class="signal-row"><span>TP / SL</span><span class="signal-val">' + formatCurrency(rec.take_profit_price) + ' / ' + formatCurrency(rec.stop_loss_price) + '</span></div>' +
                '<div class="signal-row"><span>R:R</span><span class="signal-val">' + (rec.risk_reward_ratio ? rec.risk_reward_ratio.toFixed(2) : '—') + '</span></div>';
        }

        return '<div class="signal-card">' +
            '<div class="signal-top">' +
            '<span class="signal-sym">' + rec.symbol + '</span>' +
            '<span class="badge ' + actionClass + '">' + rec.action + '</span>' +
            '</div>' +
            details +
            '<div class="signal-reason">' + rec.reasoning + '</div>' +
            '</div>';
    }).join('');

    if (recommendations.portfolio_advice) {
        html += '<div class="signal-card signal-card-full">' +
            '<div class="signal-top">' +
            '<span class="signal-sym">Portfolio advice</span>' +
            '<span class="badge badge-info">' + (recommendations.overall_market_stance || '—') + '</span>' +
            '</div>' +
            '<div class="signal-reason">' + recommendations.portfolio_advice + '</div>' +
            '</div>';
    }

    content.innerHTML = html;
}

// =====================
// Headlines / News
// =====================

async function loadHeadlines() {
    try {
        var result = await fetchAPI('/news');
        updateHeadlines(result.news || []);
    } catch (error) {
        console.error('Failed to load headlines:', error);
    }
}

function updateHeadlines(articles) {
    var container = document.getElementById('newsCards');
    if (!articles || articles.length === 0) {
        container.innerHTML = '<p class="empty-state">No news available</p>';
        return;
    }

    container.innerHTML = articles.map(function (a, i) {
        // Infer sentiment from title keywords (basic heuristic — replace with API data if available)
        var sentiment = inferSentiment(a);

        var badgeClass = sentiment === 'bullish' ? 'badge-bullish' :
            sentiment === 'bearish' ? 'badge-bearish' : 'badge-neutral';

        // Extract coin mentions
        var coins = extractCoins(a.title + ' ' + (a.body_snippet || ''));

        return '<div class="news-card" data-sentiment="' + sentiment + '" style="animation-delay:' + (i * 0.04) + 's;">' +
            '<div class="news-card-top">' +
            '<p class="news-title"><a href="' + (a.url || '#') + '" target="_blank" rel="noopener">' + a.title + '</a></p>' +
            '<span class="badge ' + badgeClass + '">' + sentiment + '</span>' +
            '</div>' +
            '<div class="news-meta">' +
            '<span class="news-source">' + a.source + '</span>' +
            '<span>' + (a.published_at || '') + '</span>' +
            '</div>' +
            (a.body_snippet ? '<p class="news-snippet">' + a.body_snippet + '</p>' : '') +
            (coins.length > 0 ?
                '<div class="news-coins">' + coins.map(function (c) { return '<span class="news-coin">' + c + '</span>'; }).join('') + '</div>'
                : '') +
            '</div>';
    }).join('');
}

function inferSentiment(article) {
    // If the API returns sentiment, use it directly
    if (article.sentiment) return article.sentiment;

    // Basic keyword heuristic fallback
    var text = ((article.title || '') + ' ' + (article.body_snippet || '')).toLowerCase();
    var bullish = ['surge', 'rally', 'gain', 'bullish', 'inflow', 'record', 'soar', 'breakout', 'grow', 'accelerat', 'optimis'];
    var bearish = ['crash', 'drop', 'bearish', 'decline', 'sell', 'fear', 'slump', 'delay', 'risk', 'spike fee', 'congest'];

    var bScore = bullish.reduce(function (s, w) { return s + (text.includes(w) ? 1 : 0); }, 0);
    var brScore = bearish.reduce(function (s, w) { return s + (text.includes(w) ? 1 : 0); }, 0);

    if (bScore > brScore) return 'bullish';
    if (brScore > bScore) return 'bearish';
    return 'neutral';
}

function extractCoins(text) {
    var coins = [];
    var upper = text.toUpperCase();
    if (upper.includes('BTC') || upper.includes('BITCOIN')) coins.push('BTC');
    if (upper.includes('ETH') || upper.includes('ETHEREUM')) coins.push('ETH');
    if (upper.includes('SOL') || upper.includes('SOLANA')) coins.push('SOL');
    return coins;
}

// News filter
function setupNewsFilters() {
    document.querySelectorAll('.filter-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            document.querySelectorAll('.filter-btn').forEach(function (b) { b.classList.remove('active'); });
            btn.classList.add('active');

            var filter = btn.dataset.filter;
            document.querySelectorAll('.news-card').forEach(function (card) {
                if (filter === 'all' || card.dataset.sentiment === filter) {
                    card.style.display = '';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    });
}

// =====================
// Logs view
// =====================

function renderLogsView() {
    renderTransactionHistory();
    renderActivityLogTable();
}

function renderTransactionHistory() {
    var el = document.getElementById('logsHistoryContent');
    if (!portfolioHistory || portfolioHistory.length === 0) {
        el.innerHTML = '<p class="empty-state">No closed trades yet</p>';
        return;
    }

    var rows = portfolioHistory.slice().reverse().map(function (trade) {
        return '<tr>' +
            '<td class="sym">' + trade.symbol + '</td>' +
            '<td class="' + (trade.direction === 'long' ? 'positive' : 'negative') + '">' + trade.direction + '</td>' +
            '<td>' + formatCurrency(trade.entry_price) + '</td>' +
            '<td>' + formatCurrency(trade.close_price) + '</td>' +
            '<td>' + (trade.leverage != null ? trade.leverage + 'x' : '—') + '</td>' +
            '<td class="' + (trade.realized_pnl >= 0 ? 'positive' : 'negative') + '">' +
            formatCurrency(trade.realized_pnl) +
            (trade.realized_pnl_percent != null ? ' (' + formatPercent(trade.realized_pnl_percent) + ')' : '') +
            '</td>' +
            '<td>' + (trade.close_reason || '—') + '</td>' +
            '<td>' + (trade.was_profitable ?
                '<span class="badge badge-success">win</span>' :
                '<span class="badge badge-danger">loss</span>') +
            '</td>' +
            '<td style="white-space:nowrap;">' + formatTime(trade.closed_at) + '</td>' +
            '</tr>';
    }).join('');

    el.innerHTML =
        '<table class="data-table">' +
        '<thead><tr>' +
        '<th>Symbol</th><th>Dir.</th><th>Entry</th><th>Exit</th><th>Lev.</th><th>P&L</th><th>Reason</th><th>Result</th><th>Closed</th>' +
        '</tr></thead>' +
        '<tbody>' + rows + '</tbody></table>';
}

function renderActivityLogTable() {
    var el = document.getElementById('logsActivityContent');
    if (activityLogs.length === 0) {
        el.innerHTML = '<p class="empty-state">No activity yet. Run agents to get started.</p>';
        return;
    }

    var rows = activityLogs.map(function (entry) {
        var tokenStr = formatTokens(entry.tokens);
        var tokenCell = tokenStr ?
            '<span style="font-family:var(--font-mono);font-size:12px;">' + tokenStr + '</span>' :
            '<span style="color:var(--text-tertiary);">—</span>';

        var badgeClass = entry.status === 'success' ? 'badge-success' :
            entry.status === 'error' ? 'badge-danger' : 'badge-info';

        return '<tr>' +
            '<td style="white-space:nowrap;font-family:var(--font-mono);font-size:12px;">' + entry.time.toLocaleTimeString() + '</td>' +
            '<td>' + entry.action + '</td>' +
            '<td>' + (entry.agent || '—') + '</td>' +
            '<td><span class="badge ' + badgeClass + '">' + entry.status + '</span></td>' +
            '<td>' + entry.details + '</td>' +
            '<td>' + tokenCell + '</td>' +
            '</tr>';
    }).join('');

    el.innerHTML =
        '<table class="data-table">' +
        '<thead><tr>' +
        '<th>Time</th><th>Action</th><th>Agent</th><th>Status</th><th>Details</th><th>Tokens</th>' +
        '</tr></thead>' +
        '<tbody>' + rows + '</tbody></table>';
}

// =====================
// P&L Chart
// =====================

function initPnlChart() {
    var canvas = document.getElementById('pnlChart');
    if (!canvas) return;

    var isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    var lineColor = isDark ? '#4ade80' : '#1a8c5b';
    var gridColor = isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)';
    var textColor = isDark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.35)';

    pnlChart = new Chart(canvas, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                data: [],
                borderColor: lineColor,
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 4,
                pointHoverBackgroundColor: lineColor,
                fill: false,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function (ctx) { return '$' + ctx.parsed.y.toLocaleString(); }
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: textColor, font: { size: 11, family: "'JetBrains Mono', monospace" } },
                    border: { display: false }
                },
                y: {
                    grid: { color: gridColor },
                    ticks: {
                        color: textColor,
                        font: { size: 11, family: "'JetBrains Mono', monospace" },
                        callback: function (v) { return '$' + v.toLocaleString(); }
                    },
                    border: { display: false }
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            }
        }
    });
}

function updatePnlChart(balanceHistory) {
    if (!pnlChart || !balanceHistory || balanceHistory.length === 0) return;

    pnlChart.data.labels = balanceHistory.map(function (pt, i) {
        if (pt.date) return pt.date;
        return 'T' + i;
    });
    pnlChart.data.datasets[0].data = balanceHistory.map(function (pt) {
        return typeof pt === 'number' ? pt : pt.balance;
    });
    pnlChart.update();
}

// =====================
// Run All Agents
// =====================

async function runAgents() {
    var btn = document.getElementById('runAgents');
    btn.disabled = true;
    btn.textContent = 'Running...';

    addActivityEntry({ action: 'Run All Agents', agent: 'System', status: 'info', details: 'Starting monitor, analysis & advisory agents...' });

    try {
        var result = await fetchAPI('/execute', { method: 'POST' });

        updatePrices(result.monitor && result.monitor.prices);
        updateAnalysis(result.analysis);
        updateRecommendations(result.recommendations);

        var stats = await fetchAPI('/portfolio/stats');
        updatePortfolio(result.portfolio, stats);

        document.getElementById('lastUpdate').textContent = 'Updated ' + new Date().toLocaleTimeString();

        var analysisTokens = (result.analysis && (result.analysis.usage || result.analysis.tokens_used)) || null;
        var advisoryTokens = (result.recommendations && (result.recommendations.usage || result.recommendations.tokens_used)) || null;

        addActivityEntry({ action: 'Run All Agents', agent: 'Monitor', status: 'success', details: 'Prices & news fetched', tokens: null });
        addActivityEntry({
            action: 'Run All Agents', agent: 'Analysis', status: 'success',
            details: 'Sentiment: ' + ((result.analysis && result.analysis.market_sentiment) || 'N/A') +
                ' | Risk: ' + ((result.analysis && result.analysis.risk_level) || 'N/A'),
            tokens: analysisTokens
        });
        addActivityEntry({
            action: 'Run All Agents', agent: 'Advisory', status: 'success',
            details: ((result.recommendations && result.recommendations.recommendations && result.recommendations.recommendations.length) || 0) + ' recommendations generated',
            tokens: advisoryTokens
        });

        if (result.opened_positions && result.opened_positions.length > 0) {
            result.opened_positions.forEach(function (pos) {
                addActivityEntry({
                    action: 'Trade Opened', agent: 'Advisory', status: 'success',
                    details: pos.direction.toUpperCase() + ' ' + pos.symbol + ' at ' + formatCurrency(pos.entry_price)
                });
            });
        }

        if (result.closed_positions && result.closed_positions.length > 0) {
            result.closed_positions.forEach(function (pos) {
                addActivityEntry({
                    action: 'Position Closed', agent: 'System',
                    status: pos.realized_pnl >= 0 ? 'success' : 'error',
                    details: pos.symbol + ' closed with ' + formatCurrency(pos.realized_pnl)
                });
            });
        }

    } catch (error) {
        addActivityEntry({ action: 'Run All Agents', agent: 'System', status: 'error', details: error.message });
    } finally {
        btn.disabled = false;
        btn.textContent = 'Run agents';
    }
}

// =====================
// Update Positions
// =====================

async function updatePositions() {
    var btn = document.getElementById('updatePositions');
    btn.disabled = true;

    addActivityEntry({ action: 'Update Positions', agent: 'System', status: 'info', details: 'Checking TP/SL levels...' });

    try {
        var result = await fetchAPI('/portfolio/update', { method: 'POST' });
        var stats = await fetchAPI('/portfolio/stats');
        updatePortfolio(result.portfolio, stats);

        if (result.closed_positions && result.closed_positions.length > 0) {
            result.closed_positions.forEach(function (pos) {
                addActivityEntry({
                    action: 'Position Closed', agent: 'System',
                    status: pos.realized_pnl >= 0 ? 'success' : 'error',
                    details: pos.symbol + ' closed with ' + formatCurrency(pos.realized_pnl)
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

        var portfolio = await fetchAPI('/portfolio');
        var stats = await fetchAPI('/portfolio/stats');
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
        var prices = await fetchAPI('/prices');
        updatePrices(prices);
    } catch (error) {
        console.error('Failed to load prices:', error);
    }
}

async function loadPortfolio() {
    try {
        var portfolio = await fetchAPI('/portfolio');
        var stats = await fetchAPI('/portfolio/stats');
        updatePortfolio(portfolio, stats);
    } catch (error) {
        console.error('Failed to load portfolio:', error);
    }
}

// =====================
// Initialize
// =====================

document.addEventListener('DOMContentLoaded', function () {
    // Load data
    loadPrices();
    loadPortfolio();
    loadHeadlines();
    initPnlChart();

    // Navigation
    document.querySelectorAll('.nav-item').forEach(function (btn) {
        btn.addEventListener('click', function () {
            navigateTo(btn.dataset.view);
        });
    });

    // News filters
    setupNewsFilters();

    // Action buttons
    document.getElementById('runAgents').addEventListener('click', runAgents);
    document.getElementById('updatePositions').addEventListener('click', updatePositions);
    document.getElementById('resetPortfolio').addEventListener('click', resetPortfolio);
    document.getElementById('refreshNews').addEventListener('click', loadHeadlines);

    // Auto-refresh
    setInterval(loadPrices, 30000);
    setInterval(loadHeadlines, 300000);

    addActivityEntry({ action: 'System Start', agent: 'System', status: 'success', details: 'Perple initialized' });
});
