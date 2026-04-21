/**
 * SaaS UI Controller - Multi-User Management with Mode Sync
 */

document.addEventListener('DOMContentLoaded', async () => {
    // Auth Components
    const authOverlay = document.getElementById('auth-overlay');
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const authStatus = document.getElementById('auth-status');
    
    // Modals
    const adminOverlay = document.getElementById('admin-overlay');
    const profileOverlay = document.getElementById('profile-overlay');
    
    // Controls
    const modeToggle = document.getElementById('mode-toggle');
    const engineStatus = document.getElementById('engine-status');

    // Header Info
    const headerUser = document.getElementById('header-username');
    const subStatus = document.getElementById('sub-status');
    const expiryDisplay = document.getElementById('expiry-display');
    const accessType = document.getElementById('access-type');

    // --- AUTH FLOW ---

    document.getElementById('show-register').onclick = () => {
        loginForm.style.display = 'none';
        registerForm.style.display = 'block';
    };

    document.getElementById('show-login').onclick = () => {
        loginForm.style.display = 'block';
        registerForm.style.display = 'none';
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
            updateUIState(data);
            initApp();
        } else {
            authStatus.textContent = data.message;
            authStatus.style.color = '#ef4444';
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
            alert("Registration successful! Please login.");
            document.getElementById('show-login').click();
        } else {
            alert(data.message);
        }
    };

    function updateUIState(data) {
        headerUser.textContent = data.username;
        subStatus.textContent = data.is_active ? 'Active' : 'Inactive';
        subStatus.className = `sub-tag ${data.is_active ? 'active' : ''}`;
        expiryDisplay.textContent = data.expiry || 'N/A';
        accessType.textContent = data.role.toUpperCase();
        
        // Sync Mode Toggle
        modeToggle.checked = (data.trading_mode === 'LIVE');
        updateModeDisplay(data.trading_mode);

        if (data.role === 'admin') {
            document.getElementById('admin-btn').style.display = 'inline-block';
        }
    }

    // --- MODE TOGGLE SYNC ---

    modeToggle.addEventListener('change', async () => {
        const mode = modeToggle.checked ? 'LIVE' : 'PAPER';
        updateModeDisplay(mode);

        await fetch('/api/user/mode', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ mode })
        });
        console.log(`Trading mode updated to: ${mode}`);
    });

    function updateModeDisplay(mode) {
        const engineStatusDot = document.getElementById('engine-status-dot');
        if (mode === 'LIVE') {
            engineStatus.textContent = 'LIVE';
            engineStatus.style.color = 'var(--danger)';
            if (engineStatusDot) engineStatusDot.style.background = 'var(--danger)';
        } else {
            engineStatus.textContent = 'PAPER';
            engineStatus.style.color = 'var(--accent)';
            if (engineStatusDot) engineStatusDot.style.background = 'var(--accent)';
        }
    }

    // --- MODAL CONTROLS ---

    document.getElementById('profile-btn').onclick = async () => {
        profileOverlay.classList.add('active');
        const res = await fetch('/api/user/config');
        const config = await res.json();
        if (config) {
            document.getElementById('api-key').value = config.api_key || '';
            document.getElementById('client-code').value = config.client_code || '';
            document.getElementById('trading-pass').value = config.password || ''; // New
            document.getElementById('totp-secret').value = config.totp_secret || '';
            document.getElementById('redirect-url').value = config.redirect_url || '';
            document.getElementById('totp-url').value = config.totp_app_url || '';
            document.getElementById('callback-url-display').value = config.callback_url || '';
            document.getElementById('postback-url-display').value = config.postback_url || '';
            document.getElementById('static-ip-display').value = config.static_ip || '103.212.120.45';
        }
    };

    document.getElementById('admin-btn').onclick = async () => {
        adminOverlay.classList.add('active');
        loadUsers();
    };

    document.querySelectorAll('.close-modal').forEach(btn => {
        btn.onclick = () => {
            adminOverlay.classList.remove('active');
            profileOverlay.classList.remove('active');
        };
    });

    document.getElementById('save-config-btn').onclick = async () => {
        const config = {
            api_key: document.getElementById('api-key').value,
            client_code: document.getElementById('client-code').value,
            password: document.getElementById('trading-pass').value, // New
            totp_secret: document.getElementById('totp-secret').value,
            redirect_url: document.getElementById('redirect-url').value,
            totp_app_url: document.getElementById('totp-url').value
        };
        
        const res = await fetch('/api/user/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        
        if ((await res.json()).success) {
            alert("Configuration saved! Attempting background SDK login...");
            profileOverlay.classList.remove('active');
        }
    };

    async function loadUsers() {
        const res = await fetch('/api/admin/users');
        const users = await res.json();
        const tbody = document.getElementById('user-list-body');
        tbody.innerHTML = '';
        
        users.forEach(u => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${u.username}</td>
                <td><span class="sub-tag ${u.is_active ? 'active' : ''}">${u.is_active ? 'Active' : 'Inactive'}</span></td>
                <td>${u.expiry}</td>
                <td>
                    <button class="action-btn ${u.is_active ? 'disable' : 'enable'}" onclick="toggleUser(${u.id})">
                        ${u.is_active ? 'Disable' : 'Enable (30d)'}
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    window.toggleUser = async (id) => {
        await fetch('/api/admin/toggle_user', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ user_id: id })
        });
        loadUsers();
    };

    document.getElementById('logout-btn').onclick = () => {
        window.location.reload();
    };

    document.getElementById('copy-callback-btn').onclick = () => {
        copyToClipboard('callback-url-display', 'copy-callback-btn');
    };

    document.getElementById('copy-postback-btn').onclick = () => {
        copyToClipboard('postback-url-display', 'copy-postback-btn');
    };

    document.getElementById('copy-ip-btn').onclick = () => {
        copyToClipboard('static-ip-display', 'copy-ip-btn');
    };

    function copyToClipboard(inputId, btnId) {
        const urlField = document.getElementById(inputId);
        urlField.select();
        document.execCommand('copy');
        
        const btn = document.getElementById(btnId);
        const originalText = btn.textContent;
        btn.textContent = 'Copied!';
        btn.style.background = 'var(--accent)';
        setTimeout(() => {
            btn.textContent = originalText;
            btn.style.background = 'var(--success)';
        }, 2000);
    }

    // --- APP LOGIC ---

    function initApp() {
        // Initial load
        updateDashboardData();
        
        setInterval(() => {
            const engineStatusDot = document.getElementById('engine-status-dot');
            engineStatus.textContent = modeToggle.checked ? 'LIVE' : 'PAPER';
            if (engineStatusDot) {
                engineStatusDot.classList.add('online');
                engineStatusDot.style.background = modeToggle.checked ? 'var(--danger)' : 'var(--success)';
            }
            updateMockScanner();
            updateDashboardData();
        }, 5000);
    }

    async function updateDashboardData() {
        try {
            // Fetch P&L Stats
            const statsRes = await fetch('/api/user/stats');
            const stats = await statsRes.json();
            
            // Daily P&L
            const pnlDisplay = document.getElementById('display-pnl');
            if (pnlDisplay) {
                pnlDisplay.textContent = `₹${stats.daily_pnl.toFixed(2)}`;
                pnlDisplay.className = `stat-value ${stats.daily_pnl >= 0 ? 'success' : 'danger'}`;
            }

            // Total Real Profit
            const totalProfitDisplay = document.getElementById('total-profit');
            if (totalProfitDisplay) {
                totalProfitDisplay.textContent = `₹${stats.total_real_profit.toFixed(2)}`;
                totalProfitDisplay.className = `value ${stats.total_real_profit >= 0 ? 'success' : 'danger'}`;
            }

            // CAGR
            const cagrDisplay = document.getElementById('cagr-value');
            if (cagrDisplay) {
                cagrDisplay.textContent = `${stats.cagr.toFixed(2)}%`;
            }

            // Global Market Status Flag
            window.isMarketOpen = stats.is_market_open;

            // Fetch Active Positions
            const posRes = await fetch('/api/user/positions');
            const positions = await posRes.json();
            const posContainer = document.getElementById('active-trade-container');
            
            if (positions.length === 0) {
                posContainer.innerHTML = `
                    <div class="empty-trades">
                        <div class="radar-animation ${!stats.is_market_open ? 'paused' : ''}">
                            <span></span><span></span><span></span>
                        </div>
                        <p>${stats.is_market_open ? 'Scanning for high-probability signals...' : 'Market is currently closed'}</p>
                    </div>
                `;
            } else {
                posContainer.innerHTML = '';
                positions.forEach(p => {
                    const card = document.createElement('div');
                    card.className = 'index-card position-card';
                    const totalPnl = p.realized + p.unrealized;
                    card.innerHTML = `
                        <div class="top-row">
                            <span class="index-name">${p.symbol}</span>
                            <span class="pnl-badge ${totalPnl >= 0 ? 'success' : 'danger'}">₹${totalPnl.toFixed(2)}</span>
                        </div>
                        <div class="index-metrics">
                            <div class="metric">Qty: <span>${p.qty}</span></div>
                            <div class="metric">Avg: <span>${p.avg_price.toFixed(2)}</span></div>
                        </div>
                    `;
                    posContainer.appendChild(card);
                });
            }
        } catch (e) {
            console.error("Dashboard Update Error:", e);
        }
    }

    function updateMockScanner() {
        const indices = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY'];
        const list = document.getElementById('indices-list');
        list.innerHTML = '';
        
        indices.forEach(name => {
            const card = document.createElement('div');
            card.className = 'index-card';
            const isOpen = window.isMarketOpen !== false;
            card.innerHTML = `
                <div class="top-row">
                    <span class="index-name">${name}</span>
                    <span class="index-score ${isOpen ? 'high' : 'neutral'}">${isOpen ? '82' : '--'}</span>
                </div>
                <div class="index-metrics">
                    <div class="metric">Status: <span>${isOpen ? 'MONITORING' : 'MARKET CLOSED'}</span></div>
                    <div class="metric">Server: <span>${isOpen ? 'SDK SYNCED' : 'IDLE'}</span></div>
                </div>
            `;
            list.appendChild(card);
        });
    }
});
