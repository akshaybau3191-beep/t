import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { 
  Home, 
  TrendingUp, 
  User, 
  Settings as SettingsIcon, 
  ShieldAlert, 
  LogOut,
  Bell,
  Cpu,
  Terminal,
  Zap,
  Play
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import TradesView from './components/TradesView';
import SettingsView from './components/SettingsView';
import AdminView from './components/AdminView';

// Configure Axios
axios.defaults.withCredentials = true;

const Auth = ({ onLogin }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const endpoint = isLogin ? '/api/auth/login' : '/api/auth/register';
      const res = await axios.post(endpoint, { username, password });
      if (res.data.success) {
        if (isLogin) {
          onLogin(res.data);
        } else {
          setIsLogin(true);
          alert('Registration successful! Please login.');
        }
      } else {
        setError(res.data.message);
      }
    } catch (err) {
      setError('Connection error');
    }
  };

  return (
    <div className="auth-container fade-in">
      <div className="premium-bg" />
      <div className="auth-card glass">
        <h1 className="auth-title">Elite Access</h1>
        <p className="auth-subtitle">{isLogin ? 'Sign in to your trading desk' : 'Create a new account'}</p>
        <form onSubmit={handleSubmit}>
          <div className="input-group">
            <input type="text" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} className="m3-input" required />
          </div>
          <div className="input-group">
            <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} className="m3-input" required />
          </div>
          {error && <p className="error-text">{error}</p>}
          <button type="submit" className="m3-btn primary">{isLogin ? 'Sign In' : 'Create Account'}</button>
        </form>
        <p className="auth-toggle">
          {isLogin ? "Don't have an account?" : "Already have an account?"}{' '}
          <span onClick={() => setIsLogin(!isLogin)} className="toggle-link">{isLogin ? 'Sign Up' : 'Sign In'}</span>
        </p>
      </div>
    </div>
  );
};

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [indices, setIndices] = useState([]);
  const [logs, setLogs] = useState([]);
  const logEndRef = useRef(null);

  const fetchStats = async () => {
    try {
      const [resStats, resIndices, resLogs] = await Promise.all([
        axios.get('/api/user/stats'),
        axios.get('/api/market/indices'),
        axios.get('/api/user/engine_logs')
      ]);
      setStats(resStats.data);
      setIndices(resIndices.data);
      setLogs(resLogs.data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const toggleMode = async () => {
    const res = await axios.post('/api/user/toggle_mode');
    if (res.data.success) {
       fetchStats();
    }
  };

  return (
    <div className="dashboard-view fade-in">
      <div className="top-control-row">
         <div className="execution-mode-card glass">
            <div className="mode-info">
               <Zap size={16} className={stats?.trading_mode === 'LIVE' ? 'icon-live' : 'icon-paper'} />
               <span>Execution: <strong>{stats?.trading_mode || 'PAPER'}</strong></span>
            </div>
            <button onClick={toggleMode} className={`mode-toggle-btn ${stats?.trading_mode === 'LIVE' ? 'live' : 'paper'}`}>
               SWITCH TO {stats?.trading_mode === 'LIVE' ? 'PAPER' : 'LIVE'}
            </button>
         </div>
         <div className="quick-actions">
            {stats?.user_role === 'admin' && (
              <button onClick={() => axios.post('/api/admin/start_engine')} className="action-btn-circle" title="Restart Engine">
                 <Play size={18} />
              </button>
            )}
         </div>
      </div>

      <div className="stats-grid">
        <div className="m3-card scanner-card">
          <div className="card-header">
            <Cpu size={20} className="icon-accent" />
            <h3>AI Engine Scanner</h3>
          </div>
          <div className="scanner-status">
            <div className="status-header">
              <div className={`status-pill ${stats?.engine_status === 'Online' ? 'active' : 'offline'}`}>
                {stats?.engine_status || 'Offline'}
              </div>
              <div className="task-name">{stats?.engine_task || 'Waiting...'}</div>
            </div>
            <div className="task-details">
              <span>{stats?.scanned_count || 0} Scripts Analysed</span>
              <span className="live-badge">NIFTY ONLY</span>
            </div>
          </div>
        </div>

        <div className="m3-card pnl-card">
          <h3>Portfolio P&L</h3>
          <div className="pnl-value" style={{ color: stats?.daily_pnl >= 0 ? 'var(--success)' : 'var(--danger)' }}>
            ₹{stats?.daily_pnl?.toFixed(2) || '0.00'}
          </div>
          <p>Real Profit: ₹{stats?.total_real_profit?.toFixed(2) || '0.00'}</p>
        </div>
      </div>

      <div className="terminal-container m3-card">
         <div className="terminal-header">
            <Terminal size={16} />
            <span>AI Engine Live Console</span>
         </div>
         <div className="terminal-content">
            {logs.length > 0 ? logs.map((log, i) => (
               <div key={i} className="log-line">{log}</div>
            )) : <div className="log-line opacity-50">Waiting for logs...</div>}
            <div ref={logEndRef} />
         </div>
      </div>

      <div className="indices-row">
        {indices.map((idx) => (
          <div key={idx.name} className="index-chip glass">
            <span className="index-name">{idx.name}</span>
            <span className="index-ltp">{idx.ltp}</span>
          </div>
        ))}
      </div>

      <style>{`
        .dashboard-view { padding: 20px; }
        .top-control-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; gap: 16px; }
        .execution-mode-card { display: flex; align-items: center; gap: 20px; padding: 12px 24px; border-radius: 16px; flex: 1; }
        .mode-info { display: flex; align-items: center; gap: 10px; font-size: 14px; }
        .icon-live { color: #f44336; }
        .icon-paper { color: #4caf50; }
        .mode-toggle-btn { padding: 8px 16px; border-radius: 8px; border: none; font-size: 11px; font-weight: 700; cursor: pointer; transition: 0.2s; }
        .mode-toggle-btn.paper { background: rgba(76, 175, 80, 0.2); color: #4caf50; }
        .mode-toggle-btn.live { background: rgba(244, 67, 54, 0.2); color: #f44336; }
        .action-btn-circle { width: 40px; height: 40px; border-radius: 50%; border: 1px solid var(--glass-border); background: rgba(255,255,255,0.05); color: var(--accent); cursor: pointer; display: flex; align-items: center; justify-content: center; }
        
        .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }
        .m3-card { background: rgba(255, 255, 255, 0.05); padding: 24px; border-radius: 24px; border: 1px solid var(--glass-border); }
        .status-header { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
        .status-pill { padding: 4px 8px; border-radius: 6px; font-size: 10px; font-weight: 700; text-transform: uppercase; }
        .status-pill.active { background: rgba(76, 175, 80, 0.2); color: #4caf50; border: 1px solid rgba(76, 175, 80, 0.3); }
        .status-pill.offline { background: rgba(244, 67, 54, 0.2); color: #f44336; border: 1px solid rgba(244, 67, 54, 0.3); }
        .task-name { font-size: 18px; font-weight: 700; color: var(--accent); }
        
        .terminal-container { background: #000; border: 1px solid #333; padding: 16px; height: 250px; display: flex; flex-direction: column; margin-bottom: 24px; }
        .terminal-header { display: flex; align-items: center; gap: 10px; font-size: 12px; color: #666; margin-bottom: 12px; border-bottom: 1px solid #222; padding-bottom: 8px; }
        .terminal-content { flex: 1; overflow-y: auto; font-family: 'JetBrains Mono', monospace; font-size: 11px; line-height: 1.6; color: #0f0; }
        .log-line { margin-bottom: 4px; }
        
        .indices-row { display: flex; gap: 12px; overflow-x: auto; padding-bottom: 8px; }
        .index-chip { padding: 12px 20px; border-radius: 100px; background: rgba(255, 255, 255, 0.05); display: flex; gap: 12px; white-space: nowrap; border: 1px solid var(--glass-border); }
        .index-ltp { font-weight: 700; color: var(--accent); }
      `}</style>
    </div>
  );
};

const App = () => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeView, setActiveView] = useState('home');

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const res = await axios.get('/api/auth/me');
        if (res.data.success) { setUser(res.data); }
      } catch (err) { console.error('Auth check failed'); } finally { setLoading(false); }
    };
    checkAuth();
  }, []);

  if (loading) return <div className="loader">Initializing...</div>;
  if (!user) return <Auth onLogin={setUser} />;

  return (
    <div className="app-shell">
      <div className="premium-bg" />
      <header className="main-header glass">
        <div className="header-left">
          <h1 className="logo">Elite Trader</h1>
          <div className="status-dot-container">
            <div className="dot pulse" />
            <span>Market Live</span>
          </div>
        </div>
        <div className="header-right">
          <Bell size={20} />
          <div className="user-avatar" onClick={() => setActiveView('profile')}>{user.username[0].toUpperCase()}</div>
        </div>
      </header>

      <main className="content-area">
        <AnimatePresence mode="wait">
          {activeView === 'home' && <Dashboard key="home" />}
          {activeView === 'trades' && <TradesView key="trades" />}
          {activeView === 'settings' && <SettingsView key="settings" />}
          {activeView === 'admin' && <AdminView key="admin" />}
          {activeView === 'profile' && (
             <motion.div initial={{opacity:0, y: 10}} animate={{opacity:1, y: 0}} exit={{opacity:0, y: -10}} className="profile-view" style={{ padding: '20px' }}>
               <div className="m3-card">
                  <div className="profile-header">
                    <div className="avatar-large">{user.username[0].toUpperCase()}</div>
                    <h2>{user.username}</h2>
                    <p className="role-tag">{user.role}</p>
                  </div>
                  <button onClick={async () => { await axios.post('/api/auth/logout'); setUser(null); }} className="m3-btn danger" style={{ marginTop: '32px' }}>
                    <LogOut size={18} style={{ marginRight: '8px' }} /> Logout
                  </button>
               </div>
             </motion.div>
          )}
        </AnimatePresence>
      </main>

      <nav className="bottom-nav glass">
        <div className={`nav-item ${activeView === 'home' ? 'active' : ''}`} onClick={() => setActiveView('home')}><Home size={24} /><span>Home</span></div>
        <div className={`nav-item ${activeView === 'trades' ? 'active' : ''}`} onClick={() => setActiveView('trades')}><TrendingUp size={24} /><span>Trades</span></div>
        <div className={`nav-item ${activeView === 'profile' ? 'active' : ''}`} onClick={() => setActiveView('profile')}><User size={24} /><span>Profile</span></div>
        <div className={`nav-item ${activeView === 'settings' ? 'active' : ''}`} onClick={() => setActiveView('settings')}><SettingsIcon size={24} /><span>Settings</span></div>
        {user.role === 'admin' && <div className={`nav-item ${activeView === 'admin' ? 'active' : ''}`} onClick={() => setActiveView('admin')}><ShieldAlert size={24} /><span>Admin</span></div>}
      </nav>

      <style>{`
        .app-shell { min-height: 100vh; padding-bottom: 80px; }
        .main-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; position: sticky; top: 0; z-index: 100; backdrop-filter: blur(10px); border-bottom: 1px solid var(--glass-border); }
        .logo { font-size: 20px; font-weight: 700; }
        .status-dot-container { display: flex; align-items: center; gap: 8px; font-size: 12px; margin-top: 2px; }
        .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success); }
        .pulse { animation: pulse 2s infinite; }
        @keyframes pulse { 0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7); } 70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(76, 175, 80, 0); } 100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(76, 175, 80, 0); } }
        .header-right { display: flex; align-items: center; gap: 16px; }
        .user-avatar { width: 36px; height: 36px; border-radius: 50%; background: var(--primary); display: flex; align-items: center; justify-content: center; font-weight: 700; cursor: pointer; }
        .bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; height: 72px; display: flex; justify-content: space-around; align-items: center; background: rgba(30, 26, 36, 0.95); backdrop-filter: blur(20px); border-top: 1px solid var(--glass-border); padding: 0 10px; z-index: 1000; }
        .nav-item { display: flex; flex-direction: column; align-items: center; gap: 4px; color: var(--dark-on-surface-variant); cursor: pointer; transition: color 0.3s; flex: 1; }
        .nav-item.active { color: var(--accent); }
        .nav-item span { font-size: 11px; font-weight: 500; }
        .loader { height: 100vh; display: flex; align-items: center; justify-content: center; font-size: 18px; }
        .m3-btn.danger { background: var(--danger); }
      `}</style>
    </div>
  );
};

export default App;
