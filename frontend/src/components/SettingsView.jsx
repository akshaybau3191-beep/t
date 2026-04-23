import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Shield, Briefcase, Info, Copy, Target, AlertTriangle } from 'lucide-react';

const SettingsView = () => {
  const [riskConfig, setRiskConfig] = useState({
    risk: { total_capital: 100000, max_daily_loss_pct: 3, risk_per_trade_pct: 2 },
    strategy: { min_confidence_score: 75 }
  });
  const [brokerConfig, setBrokerConfig] = useState({
    api_key: '', api_secret: '', client_code: '', password: '', totp_secret: '',
    callback_url: 'https://smartapi.angelone.in/publisher-login', 
    postback_url: '', static_ip: '13.233.123.45' // Example or fetched
  });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [resRisk, resBroker] = await Promise.all([
          axios.get('/api/user/risk-config'),
          axios.get('/api/user/broker-config')
        ]);
        setRiskConfig(resRisk.data);
        setBrokerConfig(prev => ({...prev, ...resBroker.data}));
      } catch (err) {
        console.error(err);
      }
    };
    fetchData();
  }, []);

  const saveRisk = async () => {
    await axios.post('/api/user/risk-config', riskConfig);
    alert('Risk & Strategy configuration saved!');
  };

  const saveBroker = async () => {
    try {
      const res = await axios.post('/api/user/broker-config', brokerConfig);
      alert(res.data.message || 'Broker configuration saved!');
    } catch (err) {
      alert('Error saving configuration.');
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    alert('Copied to clipboard!');
  };

  return (
    <div className="settings-view fade-in">
      <div className="section-header">
        <Shield size={20} className="icon-accent" />
        <h2>Risk & Strategy</h2>
      </div>
      
      <div className="m3-card settings-card">
        <div className="input-row">
          <div className="input-group">
            <label>Total Capital Deployment (₹)</label>
            <input 
              type="number" 
              value={riskConfig.risk.total_capital}
              onChange={(e) => setRiskConfig({...riskConfig, risk: {...riskConfig.risk, total_capital: e.target.value}})}
              className="m3-input"
            />
          </div>
        </div>
        <div className="input-grid">
          <div className="input-group">
            <label>Daily Loss Limit (%)</label>
            <input 
              type="number" 
              value={riskConfig.risk.max_daily_loss_pct}
              onChange={(e) => setRiskConfig({...riskConfig, risk: {...riskConfig.risk, max_daily_loss_pct: e.target.value}})}
              className="m3-input"
            />
          </div>
          <div className="input-group">
            <label>Risk Per Trade (%)</label>
            <input 
              type="number" 
              value={riskConfig.risk.risk_per_trade_pct}
              onChange={(e) => setRiskConfig({...riskConfig, risk: {...riskConfig.risk, risk_per_trade_pct: e.target.value}})}
              className="m3-input"
            />
          </div>
        </div>
        
        <div className="input-group" style={{ marginTop: '12px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Target size={14} /> Min Confidence Threshold (%)
          </label>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <input 
              type="range" 
              min="50" 
              max="95" 
              step="5"
              value={riskConfig.strategy.min_confidence_score}
              onChange={(e) => setRiskConfig({...riskConfig, strategy: {...riskConfig.strategy, min_confidence_score: e.target.value}})}
              style={{ flex: 1, accentColor: 'var(--accent)' }}
            />
            <span className="confidence-value">{riskConfig.strategy.min_confidence_score}%</span>
          </div>
          <p className="input-hint">The AI will only execute trades above this confidence level.</p>
        </div>

        <button onClick={saveRisk} className="m3-btn primary-btn">Save Risk Controls</button>
      </div>

      <div className="section-header" style={{ marginTop: '32px' }}>
        <Briefcase size={20} className="icon-accent" />
        <h2>Broker Configuration (Angel One)</h2>
        <div className={`trading-mode-pill ${brokerConfig.trading_mode === 'LIVE' ? 'live' : 'paper'}`}>
          {brokerConfig.trading_mode} MODE
        </div>
      </div>

      <div className="m3-card settings-card">
        <div className="input-grid">
          <div className="input-group">
            <label>API Key</label>
            <input 
              type="password" 
              value={brokerConfig.api_key}
              onChange={(e) => setBrokerConfig({...brokerConfig, api_key: e.target.value})}
              className="m3-input"
            />
          </div>
          <div className="input-group">
            <label>API Secret</label>
            <input 
              type="password" 
              value={brokerConfig.api_secret}
              onChange={(e) => setBrokerConfig({...brokerConfig, api_secret: e.target.value})}
              className="m3-input"
              placeholder="Enter SmartAPI Secret"
            />
          </div>
        </div>
        <div className="input-grid">
          <div className="input-group">
            <label>Client Code</label>
            <input 
              type="text" 
              value={brokerConfig.client_code}
              onChange={(e) => setBrokerConfig({...brokerConfig, client_code: e.target.value})}
              className="m3-input"
            />
          </div>
          <div className="input-group">
            <label>Trading PIN / Password</label>
            <input 
              type="password" 
              value={brokerConfig.password}
              onChange={(e) => setBrokerConfig({...brokerConfig, password: e.target.value})}
              className="m3-input"
              placeholder="Enter your 4-digit PIN or Password"
            />
          </div>
        </div>
        <div className="input-group">
          <label>TOTP Secret</label>
          <input 
            type="password" 
            value={brokerConfig.totp_secret}
            onChange={(e) => setBrokerConfig({...brokerConfig, totp_secret: e.target.value})}
            className="m3-input"
            placeholder="Enter secret key from Angel One"
          />
        </div>
        <button onClick={saveBroker} className="m3-btn secondary-btn">Save Broker Settings</button>
      </div>

      <div className="section-header" style={{ marginTop: '32px' }}>
        <Info size={20} className="icon-accent" />
        <h2>System & Developer Info</h2>
      </div>

      <div className="m3-card info-card">
        <div className="info-item">
          <div>
            <div className="info-label">Static IP for Whitelisting</div>
            <div className="info-value">{brokerConfig.static_ip || 'Fetching...'}</div>
          </div>
          <button className="icon-btn" onClick={() => copyToClipboard(brokerConfig.static_ip)}><Copy size={16} /></button>
        </div>
        
        <div className="info-item">
          <div>
            <div className="info-label">Callback URL</div>
            <div className="info-value url">{brokerConfig.callback_url}</div>
          </div>
          <button className="icon-btn" onClick={() => copyToClipboard(brokerConfig.callback_url)}><Copy size={16} /></button>
        </div>

        <div className="info-item">
          <div>
            <div className="info-label">Postback URL (for Order Status)</div>
            <div className="info-value url">{brokerConfig.postback_url || `https://trade.truehealthayurveda.com/api/angel/postback/${brokerConfig.client_code}`}</div>
          </div>
          <button className="icon-btn" onClick={() => copyToClipboard(brokerConfig.postback_url || `https://trade.truehealthayurveda.com/api/angel/postback/${brokerConfig.client_code}`)}><Copy size={16} /></button>
        </div>
      </div>

      <div className="alert-card warning">
         <AlertTriangle size={18} />
         <div>
            <strong>Caution:</strong> Live trading involves risk. Ensure your capital and risk settings are correct before switching to LIVE mode.
         </div>
      </div>

      <style>{`
        .settings-view { padding: 24px; max-width: 900px; margin: 0 auto; }
        .settings-card { display: flex; flex-direction: column; gap: 20px; background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.05); }
        .input-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .input-group label { display: block; font-size: 13px; margin-bottom: 8px; font-weight: 500; color: rgba(255, 255, 255, 0.9); }
        .input-hint { font-size: 11px; color: rgba(255, 255, 255, 0.4); margin-top: 6px; }
        .confidence-value { font-weight: 700; color: var(--accent); min-width: 40px; text-align: right; }
        .info-card { display: flex; flex-direction: column; gap: 24px; }
        .info-item { display: flex; justify-content: space-between; align-items: center; padding-bottom: 12px; border-bottom: 1px solid rgba(255, 255, 255, 0.05); }
        .info-item:last-child { border-bottom: none; padding-bottom: 0; }
        .info-label { font-size: 11px; opacity: 0.5; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 600; }
        .info-value { font-weight: 600; margin-top: 6px; font-family: 'JetBrains Mono', monospace; color: var(--accent); }
        .info-value.url { font-size: 12px; word-break: break-all; opacity: 0.8; }
        .icon-btn { background: rgba(255, 255, 255, 0.05); border: none; color: var(--accent); cursor: pointer; padding: 10px; border-radius: 8px; transition: 0.2s; }
        .icon-btn:hover { background: rgba(255, 255, 255, 0.1); }
        .primary-btn { background: var(--accent); color: #000; font-weight: 600; }
        .secondary-btn { background: rgba(255, 255, 255, 0.1); color: #fff; }
        
        .trading-mode-pill { font-size: 10px; padding: 4px 10px; border-radius: 4px; font-weight: 800; letter-spacing: 1px; }
        .trading-mode-pill.paper { background: rgba(255, 255, 255, 0.1); color: #fff; }
        .trading-mode-pill.live { background: rgba(244, 67, 54, 0.2); color: #f44336; border: 1px solid rgba(244, 67, 54, 0.3); }

        .mode-toggle { display: flex; background: rgba(255,255,255,0.05); padding: 4px; border-radius: 12px; }
        .mode-toggle button { flex: 1; border: none; padding: 10px; border-radius: 8px; background: transparent; color: #fff; cursor: pointer; font-size: 12px; font-weight: 600; transition: 0.3s; }
        .mode-toggle button.active { background: var(--accent); color: #000; }

        .alert-card.warning { margin-top: 32px; display: flex; gap: 16px; background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.2); padding: 16px; border-radius: 12px; color: #f59e0b; align-items: flex-start; }
        .alert-card.warning strong { color: #fbbf24; }
      `}</style>
    </div>
  );
};

export default SettingsView;
