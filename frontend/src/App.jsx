import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Home, 
  TrendingUp, 
  User, 
  Settings as SettingsIcon, 
  ShieldAlert, 
  LogOut,
  Bell,
  Cpu
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import TradesView from './components/TradesView';
import SettingsView from './components/SettingsView';
import AdminView from './components/AdminView';

// Configure Axios
axios.defaults.withCredentials = true;

// Mock/Sub-components (Will be moved to separate files later)
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
            <input 
              type="text" 
              placeholder="Username" 
              value={username} 
              onChange={(e) => setUsername(e.target.value)}
              className="m3-input"
              required
            />
          </div>
          <div className="input-group">
            <input 
              type="password" 
              placeholder="Password" 
              value={password} 
              onChange={(e) => setPassword(e.target.value)}
              className="m3-input"
              required
            />
          </div>
          {error && <p className="error-text">{error}</p>}
          <button type="submit" className="m3-btn primary">
            {isLogin ? 'Sign In' : 'Create Account'}
          </button>
        </form>
        
        <p className="auth-toggle">
          {isLogin ? "Don't have an account?" : "Already have an account?"}{' '}
          <span onClick={() => setIsLogin(!isLogin)} className="toggle-link">
            {isLogin ? 'Sign Up' : 'Sign In'}
          </span>
        </p>
      </div>
      <style>{`
        .auth-container {
          height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 20px;
        }
        .auth-card {
          width: 100%;
          max-width: 400px;
          padding: 40px;
          border-radius: 28px;
          text-align: center;
          background: rgba(30, 26, 36, 0.8);
          border: 1px solid var(--glass-border);
          backdrop-filter: var(--glass-blur);
        }
        .auth-title { font-size: 32px; margin-bottom: 8px; }
        .auth-subtitle { color: var(--dark-on-surface-variant); margin-bottom: 32px; }
        .input-group { margin-bottom: 16px; }
        .m3-input {
          width: 100%;
          padding: 16px;
          border-radius: 12px;
          border: 1px solid var(--outline);
          background: transparent;
          color: white;
          font-size: 16px;
        }
        .m3-btn {
          width: 100%;
          padding: 16px;
          border-radius: 100px;
          border: none;
          background: var(--primary);
          color: white;
          font-weight: 700;
          cursor: pointer;
          margin-top: 16px;
          transition: transform 0.2s;
        }
        .m3-btn:active { transform: scale(0.98); }
        .toggle-link { color: var(--accent); cursor: pointer; font-weight: 700; }
        .error-text { color: var(--danger); font-size: 14px; margin-top: 8px; }
        .auth-toggle { margin-top: 24px; font-size: 14px; }
        .glass { box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37); }
      `}</style>
    </div>
  );
};

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [indices, setIndices] = useState([]);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [resStats, resIndices] = await Promise.all([
          axios.get('/api/user/stats'),
          axios.get('/api/market/indices')
        ]);
        setStats(resStats.data);
        setIndices(resIndices.data);
      } catch (err) {
        console.error(err);
      }
    };
    fetchStats();
    const interval = setInterval(fetchStats, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="dashboard-view fade-in">
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
          <p>Total Real Profit: ₹{stats?.total_real_profit?.toFixed(2) || '0.00'}</p>
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
        .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }
        .m3-card {
          background: rgba(255, 255, 255, 0.05);
          padding: 24px;
          border-radius: 24px;
          border: 1px solid var(--glass-border);
        }
        .card-header { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
        .icon-accent { color: var(--accent); }
        .scanner-status { margin-top: 12px; }
        .status-header { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
        .status-pill { padding: 4px 8px; border-radius: 6px; font-size: 10px; font-weight: 700; text-transform: uppercase; }
        .status-pill.active { background: rgba(76, 175, 80, 0.2); color: #4caf50; border: 1px solid rgba(76, 175, 80, 0.3); }
        .status-pill.offline { background: rgba(244, 67, 54, 0.2); color: #f44336; border: 1px solid rgba(244, 67, 54, 0.3); }
        .task-name { font-size: 18px; font-weight: 700; color: var(--accent); }
        .task-details { display: flex; justify-content: space-between; margin-top: 8px; font-size: 12px; opacity: 0.7; }
        .pnl-value { font-size: 32px; font-weight: 700; margin: 8px 0; }
        .indices-row { display: flex; gap: 12px; overflow-x: auto; padding-bottom: 8px; }
        .index-chip {
          padding: 12px 20px;
          border-radius: 100px;
          background: rgba(255, 255, 255, 0.05);
          display: flex;
          gap: 12px;
          white-space: nowrap;
          border: 1px solid var(--glass-border);
        }
        .index-name { font-weight: 500; }
        .index-ltp { font-weight: 700; color: var(--accent); }
        .live-badge { background: var(--success); color: white; padding: 2px 8px; border-radius: 4px; font-size: 10px; }
        @media (max-width: 600px) {
          .stats-grid { grid-template-columns: 1fr; }
        }
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
        if (res.data.success) {
          setUser(res.data);
        }
      } catch (err) {
        console.error('Auth check failed');
      } finally {
        setLoading(false);
      }
    };
    checkAuth();
  }, []);

  const handleLogout = async () => {
    await axios.post('/api/auth/logout');
    setUser(null);
  };

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
          <div className="user-avatar" onClick={() => setActiveView('profile')}>
            {user.username[0].toUpperCase()}
          </div>
        </div>
      </header>

      <main className="content-area">
        <AnimatePresence mode="wait">
          {activeView === 'home' && <Dashboard key="home" />}
          {activeView === 'trades' && <TradesView key="trades" />}
          {activeView === 'settings' && <SettingsView key="settings" />}
          {activeView === 'admin' && <AdminView key="admin" />}
          {activeView === 'profile' && (
             <motion.div 
               initial={{opacity:0, y: 10}} 
               animate={{opacity:1, y: 0}} 
               exit={{opacity:0, y: -10}} 
               className="profile-view"
               style={{ padding: '20px' }}
             >
               <div className="m3-card">
                  <div className="profile-header">
                    <div className="avatar-large">{user.username[0].toUpperCase()}</div>
                    <h2>{user.username}</h2>
                    <p className="role-tag">{user.role}</p>
                  </div>
                  <div className="profile-details">
                    <div className="detail-item">
                      <span className="label">Account Status</span>
                      <span className="value" style={{ color: user.is_active ? 'var(--success)' : 'var(--danger)' }}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                  </div>
                  <button onClick={handleLogout} className="m3-btn danger" style={{ marginTop: '32px' }}>
                    <LogOut size={18} style={{ marginRight: '8px' }} />
                    Logout
                  </button>
               </div>
               <style>{`
                 .profile-header { text-align: center; margin-bottom: 32px; }
                 .avatar-large { 
                   width: 80px; height: 80px; background: var(--primary); 
                   border-radius: 50%; margin: 0 auto 16px; display: flex; 
                   align-items: center; justify-content: center; font-size: 32px; font-weight: 700;
                 }
                 .role-tag { 
                   display: inline-block; padding: 4px 12px; background: rgba(255,255,255,0.1); 
                   border-radius: 100px; font-size: 12px; margin-top: 8px; text-transform: uppercase;
                 }
                 .detail-item { display: flex; justify-content: space-between; padding: 16px 0; border-bottom: 1px solid var(--glass-border); }
                 .detail-item .label { opacity: 0.6; }
                 .detail-item .value { font-weight: 600; }
               `}</style>
             </motion.div>
          )}
        </AnimatePresence>
      </main>

      <nav className="bottom-nav glass">
        <div className={`nav-item ${activeView === 'home' ? 'active' : ''}`} onClick={() => setActiveView('home')}>
          <Home size={24} />
          <span>Home</span>
        </div>
        <div className={`nav-item ${activeView === 'trades' ? 'active' : ''}`} onClick={() => setActiveView('trades')}>
          <TrendingUp size={24} />
          <span>Trades</span>
        </div>
        <div className={`nav-item ${activeView === 'profile' ? 'active' : ''}`} onClick={() => setActiveView('profile')}>
          <User size={24} />
          <span>Profile</span>
        </div>
        <div className={`nav-item ${activeView === 'settings' ? 'active' : ''}`} onClick={() => setActiveView('settings')}>
          <SettingsIcon size={24} />
          <span>Settings</span>
        </div>
        {user.role === 'admin' && (
          <div className={`nav-item ${activeView === 'admin' ? 'active' : ''}`} onClick={() => setActiveView('admin')}>
            <ShieldAlert size={24} />
            <span>Admin</span>
          </div>
        )}
      </nav>

      <style>{`
        .app-shell { min-height: 100vh; padding-bottom: 80px; }
        .main-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 16px 20px;
          position: sticky;
          top: 0;
          z-index: 100;
          backdrop-filter: blur(10px);
          border-bottom: 1px solid var(--glass-border);
        }
        .logo { font-size: 20px; font-weight: 700; }
        .status-dot-container { display: flex; align-items: center; gap: 8px; font-size: 12px; margin-top: 2px; }
        .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success); }
        .pulse { animation: pulse 2s infinite; }
        @keyframes pulse {
          0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7); }
          70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(76, 175, 80, 0); }
          100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(76, 175, 80, 0); }
        }
        .header-right { display: flex; align-items: center; gap: 16px; }
        .user-avatar {
          width: 36px;
          height: 36px;
          border-radius: 50%;
          background: var(--primary);
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 700;
          cursor: pointer;
        }
        .bottom-nav {
          position: fixed;
          bottom: 0;
          left: 0;
          right: 0;
          height: 72px;
          display: flex;
          justify-content: space-around;
          align-items: center;
          background: rgba(30, 26, 36, 0.95);
          backdrop-filter: blur(20px);
          border-top: 1px solid var(--glass-border);
          padding: 0 10px;
          z-index: 1000;
        }
        .nav-item {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 4px;
          color: var(--dark-on-surface-variant);
          cursor: pointer;
          transition: color 0.3s;
          flex: 1;
        }
        .nav-item.active { color: var(--accent); }
        .nav-item span { font-size: 11px; font-weight: 500; }
        .loader { height: 100vh; display: flex; align-items: center; justify-content: center; font-size: 18px; }
        .m3-btn.danger { background: var(--danger); }
      `}</style>
    </div>
  );
};

export default App;
