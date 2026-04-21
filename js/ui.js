/**
 * Elite Trader UI Controller - Material Design 3 (Android)
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
        }
    }

    navDests.forEach(dest => {
        dest.onclick = () => navigate(dest.dataset.view);
    });

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
        }
        
        updateStats();
        updateScanner();
        loadConfig();

        setInterval(() => {
            updateStats();
            updateScanner();
        }, 5000);
    }

    async function loadConfig() {
        const res = await fetch('/api/user/config');
        const config = await res.json();
        if (config) {
            document.getElementById('api-key').value = config.api_key || '';
            document.getElementById('client-code').value = config.client_code || '';
            document.getElementById('trading-pass').value = config.password || '';
            document.getElementById('totp-secret').value = config.totp_secret || '';
            document.getElementById('callback-url-display').textContent = config.callback_url || '';
        }
    }

    document.getElementById('save-config-btn').onclick = async () => {
        const config = {
            api_key: document.getElementById('api-key').value,
            client_code: document.getElementById('client-code').value,
            password: document.getElementById('trading-pass').value,
            totp_secret: document.getElementById('totp-secret').value
        };
        const res = await fetch('/api/user/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        if ((await res.json()).success) alert("Configuration updated.");
    };

    async function updateStats() {
        try {
            const res = await fetch('/api/user/stats');
            const stats = await res.json();
            
            const pnlEl = document.getElementById('display-pnl');
            pnlEl.textContent = `₹${stats.daily_pnl.toFixed(2)}`;
            pnlEl.className = `stat-value ${stats.daily_pnl >= 0 ? 'success' : 'danger'}`;

            document.getElementById('total-profit').textContent = `₹${stats.total_real_profit.toFixed(2)}`;
            document.getElementById('total-profit').className = `stat-value ${stats.total_real_profit >= 0 ? 'success' : 'danger'}`;
            
            const dot = document.getElementById('engine-status-dot');
            const statusText = document.getElementById('engine-status');
            if (stats.is_market_open) {
                dot.classList.add('online');
                statusText.textContent = 'Active';
            } else {
                dot.classList.remove('online');
                statusText.textContent = 'Closed';
            }

            // Positions
            const posRes = await fetch('/api/user/positions');
            const positions = await posRes.json();
            const container = document.getElementById('active-trade-container');
            if (positions.length === 0) {
                container.innerHTML = '<p style="text-align:center; padding:20px; font-size:14px; color:var(--md-sys-color-on-surface-variant);">No active positions</p>';
            } else {
                container.innerHTML = '';
                positions.forEach(p => {
                    const div = document.createElement('div');
                    div.className = 'list-item';
                    const totalPnl = p.realized + p.unrealized;
                    div.innerHTML = `
                        <div class="item-info">
                            <span class="title">${p.symbol}</span>
                            <span class="subtitle">Qty: ${p.qty} | Avg: ${p.avg_price.toFixed(2)}</span>
                        </div>
                        <span class="stat-value ${totalPnl >= 0 ? 'success' : 'danger'}" style="font-size:16px;">₹${totalPnl.toFixed(2)}</span>
                    `;
                    container.appendChild(div);
                });
            }
        } catch (e) { console.error(e); }
    }

    async function updateScanner() {
        const indices = ['NIFTY', 'BANKNIFTY', 'FINNIFTY'];
        const container = document.getElementById('indices-list');
        container.innerHTML = '';
        indices.forEach(name => {
            const div = document.createElement('div');
            div.className = 'list-item';
            div.innerHTML = `
                <div class="item-info">
                    <span class="title">${name}</span>
                    <span class="subtitle">Monitoring market signals...</span>
                </div>
                <span style="font-weight:700; color:var(--accent);">84%</span>
            `;
            container.appendChild(div);
        });
    }

    document.getElementById('logout-btn').onclick = async () => {
        await fetch('/api/auth/logout', { method: 'POST' }); // I'll add this endpoint in run.py
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
});
