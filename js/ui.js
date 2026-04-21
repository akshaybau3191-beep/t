/**
 * Elite Trader UI Controller - Pro Mobile App Experience
 */

document.addEventListener('DOMContentLoaded', async () => {
    // State
    let currentUser = null;

    // View Management
    const views = document.querySelectorAll('.view-container');
    const navItems = document.querySelectorAll('.nav-item');

    function switchView(viewId) {
        views.forEach(v => v.classList.remove('active'));
        navItems.forEach(n => n.classList.remove('active'));
        
        document.getElementById(`view-${viewId}`).classList.add('active');
        document.querySelector(`[data-view="${viewId}"]`).classList.add('active');
    }

    navItems.forEach(item => {
        item.onclick = () => switchView(item.dataset.view);
    });

    // Auth
    const authOverlay = document.getElementById('auth-overlay');
    const authStatus = document.getElementById('auth-status');

    document.getElementById('show-register').onclick = () => {
        document.getElementById('login-form').style.display = 'none';
        document.getElementById('register-form').style.display = 'block';
    };

    document.getElementById('show-login').onclick = () => {
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
            authStatus.style.color = 'var(--danger)';
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
            alert("Success! Please Login.");
            document.getElementById('show-login').click();
        } else {
            alert(data.message);
        }
    };

    function initUI() {
        if (currentUser.role === 'admin') {
            document.querySelectorAll('.admin-only').forEach(el => el.style.display = 'flex');
        }
        
        // Initial data load
        updateStats();
        updateScanner();
        
        // Settings load
        loadConfig();

        // Polling
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
            document.getElementById('callback-url-display').value = config.callback_url || '';
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
        if ((await res.json()).success) alert("Settings Saved!");
    };

    async function updateStats() {
        const res = await fetch('/api/user/stats');
        const stats = await res.json();
        
        const pnlEl = document.getElementById('display-pnl');
        pnlEl.textContent = `₹${stats.daily_pnl.toFixed(2)}`;
        pnlEl.className = `stat-value ${stats.daily_pnl >= 0 ? 'success' : 'danger'}`;

        document.getElementById('total-profit').textContent = `₹${stats.total_real_profit.toFixed(2)}`;
        
        const dot = document.getElementById('engine-status-dot');
        const statusText = document.getElementById('engine-status');
        if (stats.is_market_open) {
            dot.classList.add('online');
            statusText.textContent = 'ONLINE';
        } else {
            dot.classList.remove('online');
            statusText.textContent = 'CLOSED';
        }

        // Positions
        const posRes = await fetch('/api/user/positions');
        const positions = await posRes.json();
        const container = document.getElementById('active-trade-container');
        if (positions.length === 0) {
            container.innerHTML = '<p style="font-size:12px; color:var(--text-secondary); text-align:center;">No active trades</p>';
        } else {
            container.innerHTML = '';
            positions.forEach(p => {
                const div = document.createElement('div');
                div.className = 'index-card';
                div.innerHTML = `
                    <div class="index-info">
                        <span class="name">${p.symbol}</span>
                        <span class="status">Qty: ${p.qty} | Avg: ${p.avg_price.toFixed(2)}</span>
                    </div>
                    <span class="pnl-badge ${p.realized + p.unrealized >= 0 ? 'success' : 'danger'}">₹${(p.realized + p.unrealized).toFixed(2)}</span>
                `;
                container.appendChild(div);
            });
        }
    }

    async function updateScanner() {
        const indices = ['NIFTY', 'BANKNIFTY', 'FINNIFTY'];
        const container = document.getElementById('indices-list');
        container.innerHTML = '';
        indices.forEach(name => {
            const div = document.createElement('div');
            div.className = 'index-card';
            div.innerHTML = `
                <div class="index-info">
                    <span class="name">${name}</span>
                    <span class="status">AI MONITORING...</span>
                </div>
                <div style="font-weight:800; color:var(--accent);">84</div>
            `;
            container.appendChild(div);
        });
    }

    document.getElementById('logout-btn').onclick = () => location.reload();
});
