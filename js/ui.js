/**
 * Elite Trader UI Controller - Material Design 3 (Android)
 * Full Subscription & Automation Logic
 */

document.addEventListener('DOMContentLoaded', async () => {
    let currentUser = null;

    // --- NAVIGATION ---
    const navDests = document.querySelectorAll('.nav-dest');
    const views = document.querySelectorAll('.view');

    function navigate(viewId) {
        views.forEach(v => v.classList.remove('active'));
        navDests.forEach(n => n.classList.remove('active'));
        
        const targetView = document.getElementById(`view-${viewId}`);
        const targetNav = document.querySelector(`[data-view="${viewId}"]`);
        
        if (targetView && targetNav) {
            targetView.classList.add('active');
            targetNav.classList.add('active');
            
            if (viewId === 'config') {
                loadRiskConfig();
            }
        }
    }

    navDests.forEach(dest => {
        dest.onclick = () => navigate(dest.dataset.view);
    });

    async function loadRiskConfig() {
        try {
            const res = await fetch('/api/user/risk-config');
            const config = await res.json();
            
            if (config.risk) {
                document.getElementById('conf-total-capital').value = config.risk.total_capital;
                document.getElementById('conf-max-loss').value = config.risk.max_daily_loss_pct;
                document.getElementById('conf-risk-trade').value = config.risk.risk_per_trade_pct;
            }
            if (config.strategy) {
                document.getElementById('conf-min-score').value = config.strategy.min_confidence_score;
            }
            
        } catch (e) { console.error("Error loading risk config", e); }
    }

    const saveRiskBtn = document.getElementById('save-risk-btn');
    if (saveRiskBtn) {
        saveRiskBtn.onclick = async () => {
            try {
                const config = {
                    risk: {
                        total_capital: parseFloat(document.getElementById('conf-total-capital').value),
                        max_daily_loss_pct: parseFloat(document.getElementById('conf-max-loss').value),
                        risk_per_trade_pct: parseFloat(document.getElementById('conf-risk-trade').value)
                    },
                    strategy: {
                        min_confidence_score: parseInt(document.getElementById('conf-min-score').value)
                    }
                };

                const saveRes = await fetch('/api/user/risk-config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
                const result = await saveRes.json();
                if (result.success) {
                    alert("Risk controls updated successfully!");
                    loadRiskConfig(); // Reload to verify
                } else {
                    alert("Error: " + (result.message || "Unknown error"));
                }
            } catch (e) { alert("Failed to save risk config"); }
        };
    }

    // --- AUTH ---
    const authOverlay = document.getElementById('auth-overlay');
    const authStatus = document.getElementById('auth-status');

    document.getElementById('show-register').onclick = (e) => {
        e.preventDefault();
        document.getElementById('login-form').style.display = 'none';
        document.getElementById('register-form').style.display = 'block';
    };

    document.getElementById('show-login').onclick = (e) => {
        e.preventDefault();
        document.getElementById('login-form').style.display = 'block';
        document.getElementById('register-form').style.display = 'none';
    };

    document.getElementById('login-btn').onclick = async () => {
        const username = document.getElementById('login-user').value;
        const password = document.getElementById('login-pass').value;
        
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        
        if (data.success) {
            authOverlay.classList.remove('active');
            currentUser = data;
            initUI();
        } else {
            authStatus.textContent = data.message;
            authStatus.className = 'danger';
        }
    };

    document.getElementById('register-btn').onclick = async () => {
        const username = document.getElementById('reg-user').value;
        const password = document.getElementById('reg-pass').value;
        const res = await fetch('/api/auth/register', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        if (data.success) {
            alert("Account created! Please sign in.");
            document.getElementById('show-login').click();
        } else {
            alert(data.message);
        }
    };

    // --- INITIALIZATION ---
    function initUI() {
        if (currentUser.role === 'admin') {
            document.querySelectorAll('.admin-only').forEach(el => el.style.display = 'flex');
            document.querySelectorAll('.user-only').forEach(el => el.style.display = 'none');
            loadAdminData();
        }
        
        updateStats();
        updateTrades();
        loadConfig();
        updateProfile();

        setInterval(() => {
            updateStats();
            updateTrades();
            updateAnalysis();
        }, 5000);
    }

    async function loadConfig() {
        try {
            const res = await fetch('/api/user/broker-config');
            const config = await res.json();
            if (config) {
                if (document.getElementById('api-key')) document.getElementById('api-key').value = config.api_key || '';
                if (document.getElementById('client-code')) document.getElementById('client-code').value = config.client_code || '';
                if (document.getElementById('trading-pass')) document.getElementById('trading-pass').value = config.password || '';
                if (document.getElementById('totp-secret')) document.getElementById('totp-secret').value = config.totp_secret || '';
                
                const callbackEl = document.getElementById('callback-url-display');
                const postbackEl = document.getElementById('postback-url-display');
                if (callbackEl) callbackEl.textContent = config.callback_url || 'N/A';
                if (postbackEl) postbackEl.textContent = config.postback_url || 'N/A';
                
                const modeToggle = document.getElementById('mode-toggle');
                if (modeToggle) {
                    modeToggle.checked = (config.trading_mode === 'LIVE');
                    updateModeLabel(config.trading_mode);
                }
            }
        } catch (e) { console.error("Error loading broker config", e); }
    }

    function updateModeLabel(mode) {
        const label = document.getElementById('mode-label');
        label.textContent = mode === 'LIVE' ? 'LIVE TRADING' : 'PAPER TRADING';
        label.style.color = mode === 'LIVE' ? 'var(--danger)' : 'var(--accent)';
    }

    document.getElementById('mode-toggle').onchange = async (e) => {
        const mode = e.target.checked ? 'LIVE' : 'PAPER';
        updateModeLabel(mode);
        await fetch('/api/user/mode', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ mode })
        });
    };

    document.getElementById('save-config-btn').onclick = async () => {
        const config = {
            api_key: document.getElementById('api-key').value,
            client_code: document.getElementById('client-code').value,
            password: document.getElementById('trading-pass').value,
            totp_secret: document.getElementById('totp-secret').value
        };
        
        const res = await fetch('/api/user/broker-config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        const data = await res.json();
        if (data.success) {
            alert("Broker settings saved! System will now attempt to login.");
            loadConfig(); // Reload fields
        } else {
            alert("Error saving settings");
        }
    };

    // --- SUBSCRIPTION LOGIC ---
    async function updateProfile() {
        const statusEl = document.getElementById('profile-sub-status');
        const expiryEl = document.getElementById('profile-expiry');
        const daysEl = document.getElementById('profile-days-left');
        const badgeContainer = document.getElementById('sub-request-status-badge');

        statusEl.textContent = currentUser.is_active ? 'Active Plan' : 'Inactive';
        statusEl.className = `title ${currentUser.is_active ? 'success' : 'danger'}`;
        expiryEl.textContent = `Expires: ${currentUser.expiry || 'N/A'}`;
        
        if (currentUser.expiry) {
            const exp = new Date(currentUser.expiry);
            const now = new Date();
            const diff = Math.ceil((exp - now) / (1000 * 60 * 60 * 24));
            daysEl.textContent = `${diff > 0 ? diff : 0} Days Left`;
        }

        // Fetch My Request Status
        try {
            const res = await fetch('/api/subscription/my_request');
            const data = await res.json();
            badgeContainer.innerHTML = '';
            
            if (data.success) {
                const reqTime = new Date(data.time);
                const now = new Date();
                const hoursSinceReq = (now - reqTime) / (1000 * 60 * 60);

                if (data.status === 'PENDING') {
                    badgeContainer.innerHTML = `<div class="mode-badge badge-live" style="width:100%; text-align:center; padding:10px; margin-bottom:15px; border-radius:12px; font-size:12px;">⌛ REQUEST UNDER APPROVAL</div>`;
                } else if (data.status === 'APPROVED' && hoursSinceReq < 24) {
                    badgeContainer.innerHTML = `<div class="mode-badge badge-paper" style="width:100%; text-align:center; padding:10px; margin-bottom:15px; border-radius:12px; font-size:12px;">✅ REQUEST APPROVED! PROCEED TO TRADE</div>`;
                }
            }
        } catch (e) { console.warn(e); }
    }

    document.getElementById('submit-sub-btn').onclick = async () => {
        const upiRef = document.getElementById('upi-ref-input').value;
        const proofFile = document.getElementById('proof-image-input').files[0];
        
        if (upiRef.length < 10) {
            alert("Please enter a valid 12-digit UPI Reference Number.");
            return;
        }
        
        if (!proofFile) {
            alert("Please attach a screenshot of your payment proof.");
            return;
        }

        const formData = new FormData();
        formData.append('upi_ref', upiRef);
        formData.append('proof', proofFile);
        
        const res = await fetch('/api/subscription/request', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        if (data.success) {
            alert(data.message);
            document.getElementById('upi-ref-input').value = '';
            document.getElementById('proof-image-input').value = '';
        }
    };

    // --- ADMIN LOGIC ---
    let allUsers = [];

    async function loadAdminData() {
        loadAdminUsers();
        loadAdminRequests();
    }

    async function loadAdminUsers() {
        const res = await fetch('/api/admin/users');
        allUsers = await res.json();
        renderUserList(allUsers);
        
        // Update Admin Stats
        document.getElementById('admin-total-users').textContent = allUsers.length;
        document.getElementById('admin-active-users').textContent = allUsers.filter(u => u.is_active).length;
    }

    function renderUserList(users) {
        const tbody = document.getElementById('admin-user-table-body');
        tbody.innerHTML = '';
        users.forEach(u => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><b>${u.username}</b></td>
                <td>${u.expiry}</td>
                <td>
                    <div style="display:flex; gap:10px; align-items:center;">
                        <span class="mode-badge ${u.is_active ? 'badge-paper' : 'badge-live'}">${u.is_active ? 'Active' : 'Exp'}</span>
                        <label class="switch">
                            <input type="checkbox" ${u.is_active ? 'checked' : ''} onclick="toggleUser(${u.id})">
                            <span class="slider round"></span>
                        </label>
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    document.getElementById('admin-user-search').oninput = (e) => {
        const query = e.target.value.toLowerCase();
        const filtered = allUsers.filter(u => 
            u.username.toLowerCase().includes(query) || 
            (u.mobile && u.mobile.includes(query))
        );
        renderUserList(filtered);
    };

    async function loadAdminRequests() {
        const res = await fetch('/api/admin/sub_requests');
        const reqs = await res.json();
        const tbody = document.getElementById('admin-sub-requests-table');
        
        if (reqs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:20px;">No pending requests</td></tr>';
            return;
        }
        
        tbody.innerHTML = '';
        reqs.forEach(r => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><b>${r.username}</b></td>
                <td style="font-size:11px;">${r.upi_ref}</td>
                <td>
                    ${r.proof_url ? `<a href="${r.proof_url}" target="_blank" style="color:var(--accent); font-weight:700; text-decoration:none;">VIEW ↗</a>` : '-'}
                </td>
                <td>
                    <button class="m3-btn" style="width:auto; padding:6px 12px; margin:0; font-size:11px;" onclick="approveSub(${r.id})">APPROVE</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    window.approveSub = async (id) => {
        const res = await fetch('/api/admin/approve_sub', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ id })
        });
        if ((await res.json()).success) {
            alert("Subscription Approved!");
            loadAdminData();
        }
    };

    window.toggleUser = async (id) => {
        await fetch('/api/admin/toggle_user', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ user_id: id })
        });
        loadAdminUsers();
    };

    // --- GLOBAL HELPERS ---
    window.copyText = (text) => {
        // More robust copy for mobile
        const el = document.createElement('textarea');
        el.value = text;
        document.body.appendChild(el);
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
        alert("Copied: " + text);
    };

    window.copyElementText = (id) => {
        const text = document.getElementById(id).innerText;
        window.copyText(text);
    };

    document.getElementById('logout-btn').onclick = async () => {
        await fetch('/api/auth/logout', { method: 'POST' });
        window.location.reload();
    };

    // Auto-Login Check on Load
    const checkSession = async () => {
        try {
            const res = await fetch('/api/auth/me');
            const data = await res.json();
            if (data.success) {
                authOverlay.classList.remove('active');
                currentUser = data;
                initUI();
            }
        } catch (e) {
            console.warn("Session check failed", e);
        }
    };
    checkSession();

    // --- ANALYSIS ---
    let activeAnalysisIndex = 'NIFTY';

    async function updateAnalysis() {
        try {
            const res = await fetch(`/api/market/candles/${activeAnalysisIndex}`);
            const data = await res.json();
            
            if (data.analysis) {
                const a = data.analysis;
                const scoreVal = document.getElementById('strategy-score-val');
                const scoreDetails = document.getElementById('score-details');
                
                if (scoreVal) {
                    scoreVal.textContent = `${a.total_score}%`;
                    scoreVal.style.color = a.total_score >= 75 ? 'var(--success)' : 'var(--accent)';
                }
                
                if (scoreDetails) {
                    scoreDetails.innerHTML = `
                        Trend: ${a.trend_score} | RSI: ${a.rsi_score.toFixed(1)} | MACD: ${a.macd_score} | Vol: ${a.vol_score} | Breakout: ${a.breakout_score}
                    `;
                }
            }
        } catch (e) { console.error("Analysis error:", e); }
    }

    // Initialize analysis
    updateAnalysis();
});



async function updateStats() {
    try {
        const res = await fetch('/api/user/stats');
        const stats = await res.json();
        
        const pnlEl = document.getElementById('display-pnl');
        if (pnlEl) {
            pnlEl.textContent = `₹${stats.daily_pnl.toFixed(2)}`;
            pnlEl.className = `stat-value ${stats.daily_pnl >= 0 ? 'success' : 'danger'}`;
        }

        const profEl = document.getElementById('total-profit');
        if (profEl) {
            profEl.textContent = `₹${stats.total_real_profit.toFixed(2)}`;
            profEl.className = `stat-value ${stats.total_real_profit >= 0 ? 'success' : 'danger'}`;
        }
        
        const dot = document.getElementById('engine-status-dot');
        const statusText = document.getElementById('engine-status');
        const taskText = document.getElementById('engine-task');

        if (stats.is_market_open) {
            dot.classList.add('online');
            statusText.textContent = 'Active';
        } else {
            dot.classList.remove('online');
            statusText.textContent = 'Closed';
        }

        if (taskText) {
            taskText.textContent = stats.engine_task || 'Idle';
        }

        const countText = document.getElementById('scanned-count');
        if (countText) {
            countText.textContent = `Scanning ${stats.scanned_count || 0} scripts`;
        }

        const timeText = document.getElementById('last-scan-time');
        if (timeText) {
            timeText.textContent = new Date().toLocaleTimeString();
        }

        // Sync Home "Active Positions" simplified view
        const posRes = await fetch('/api/user/positions');
        const positions = await posRes.json();
        const homeContainer = document.getElementById('active-trade-container');
        if (homeContainer) {
            homeContainer.innerHTML = '';
            if (positions.length === 0) {
                homeContainer.innerHTML = '<p style="text-align:center; padding:10px; font-size:12px; color:var(--md-sys-color-on-surface-variant);">No active positions</p>';
            } else {
                positions.forEach(p => {
                    const div = document.createElement('div');
                    div.className = 'list-item';
                    div.style.padding = '8px 0';
                    div.innerHTML = `
                        <div class="item-info">
                            <span class="title" style="font-size:14px;">${p.symbol}</span>
                        </div>
                        <span class="stat-value ${p.realized + p.unrealized >= 0 ? 'success' : 'danger'}" style="font-size:14px;">₹${(p.realized + p.unrealized).toFixed(2)}</span>
                    `;
                    homeContainer.appendChild(div);
                });
            }
        }
    } catch (e) { console.error(e); }
}

async function updateTrades() {
    try {
        // 1. Update Active Positions in Trades View
        const posRes = await fetch('/api/user/positions');
        const positions = await posRes.json();
        const activeContainer = document.getElementById('trades-active-container');
        if (activeContainer) {
            activeContainer.innerHTML = '';
            if (positions.length === 0) {
                activeContainer.innerHTML = '<p style="text-align:center; padding:20px; font-size:14px; color:var(--md-sys-color-on-surface-variant);">No active trades</p>';
            } else {
                positions.forEach(p => {
                    const div = document.createElement('div');
                    div.className = 'list-item';
                    const totalPnl = p.realized + p.unrealized;
                    const badgeClass = p.mode === 'LIVE' ? 'badge-live' : 'badge-paper';
                    div.innerHTML = `
                        <div class="item-info">
                            <span class="title">${p.symbol} <span class="mode-badge ${badgeClass}">${p.mode}</span></span>
                            <span class="subtitle">Qty: ${p.qty} | Avg: ${p.avg_price.toFixed(2)}</span>
                        </div>
                        <span class="stat-value ${totalPnl >= 0 ? 'success' : 'danger'}" style="font-size:16px;">₹${totalPnl.toFixed(2)}</span>
                    `;
                    activeContainer.appendChild(div);
                });
            }
        }

        // 2. Update Trade History
        const histRes = await fetch('/api/user/history');
        const history = await histRes.json();
        const historyContainer = document.getElementById('trades-history-container');
        if (historyContainer) {
            historyContainer.innerHTML = '';
            if (history.length === 0) {
                historyContainer.innerHTML = '<p style="text-align:center; padding:20px; font-size:14px; color:var(--md-sys-color-on-surface-variant);">No trade history</p>';
            } else {
                history.forEach(t => {
                    const div = document.createElement('div');
                    div.className = 'list-item';
                    const badgeClass = t.mode === 'LIVE' ? 'badge-live' : 'badge-paper';
                    const reasonText = t.reason ? `<div style="font-size:10px; color:var(--md-sys-color-on-surface-variant); margin-top:4px;">Reason: ${t.reason}</div>` : '';
                    div.innerHTML = `
                        <div class="item-info">
                            <span class="title">${t.symbol} <span class="mode-badge ${badgeClass}">${t.mode}</span></span>
                            <span class="subtitle">${t.type} | Qty: ${t.qty} | Price: ${t.price.toFixed(2)}</span>
                            ${reasonText}
                        </div>
                        <span class="subtitle">${t.time}</span>
                    `;
                    historyContainer.appendChild(div);
                });
            }
        }
    } catch (e) { console.error(e); }
}
