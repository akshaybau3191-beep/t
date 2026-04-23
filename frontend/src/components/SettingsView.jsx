import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Shield, Briefcase, Info, Copy } from 'lucide-react';

const SettingsView = () => {
  const [riskConfig, setRiskConfig] = useState({
    risk: { total_capital: 100000, max_daily_loss_pct: 3, risk_per_trade_pct: 2 },
    strategy: { min_confidence_score: 75 }
  });
  const [brokerConfig, setBrokerConfig] = useState({
    api_key: '', api_secret: '', client_code: '', password: '', totp_secret: '',
    callback_url: '', postback_url: '', static_ip: ''
  });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [resRisk, resBroker] = await Promise.all([
          axios.get('/api/user/risk-config'),
          axios.get('/api/user/broker-config')
        ]);
        setRiskConfig(resRisk.data);
        setBrokerConfig(resBroker.data);
      } catch (err) {
        console.error(err);
      }
    };
    fetchData();
  }, []);

  const saveRisk = async () => {
    await axios.post('/api/user/risk-config', riskConfig);
    alert('Risk configuration saved!');
  };

  const saveBroker = async () => {
    await axios.post('/api/user/broker-config', brokerConfig);
    alert('Broker configuration saved!');
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
            <label>Total Capital (₹)</label>
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
            <label>Daily Loss (%)</label>
            <input 
              type="number" 
              value={riskConfig.risk.max_daily_loss_pct}
              onChange={(e) => setRiskConfig({...riskConfig, risk: {...riskConfig.risk, max_daily_loss_pct: e.target.value}})}
              className="m3-input"
            />
          </div>
          <div className="input-group">
            <label>Risk/Trade (%)</label>
            <input 
              type="number" 
              value={riskConfig.risk.risk_per_trade_pct}
              onChange={(e) => setRiskConfig({...riskConfig, risk: {...riskConfig.risk, risk_per_trade_pct: e.target.value}})}
              className="m3-input"
            />
          </div>
        </div>
        <button onClick={saveRisk} className="m3-btn">Save Risk Controls</button>
      </div>

      <div className="section-header" style={{ marginTop: '32px' }}>
        <Briefcase size={20} className="icon-accent" />
        <h2>Broker Configuration</h2>
      </div>

      <div className="m3-card settings-card">
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
          <label>Client Code</label>
          <input 
            type="text" 
            value={brokerConfig.client_code}
            onChange={(e) => setBrokerConfig({...brokerConfig, client_code: e.target.value})}
            className="m3-input"
          />
        </div>
        <div className="input-group">
          <label>TOTP Secret</label>
          <input 
            type="text" 
            value={brokerConfig.totp_secret}
            onChange={(e) => setBrokerConfig({...brokerConfig, totp_secret: e.target.value})}
            className="m3-input"
          />
        </div>
        <button onClick={saveBroker} className="m3-btn">Save Broker Settings</button>
      </div>

      <div className="section-header" style={{ marginTop: '32px' }}>
        <Info size={20} className="icon-accent" />
        <h2>System Information</h2>
      </div>

      <div className="m3-card info-card">
        <div className="info-item">
          <div>
            <div className="info-label">Static IP</div>
            <div className="info-value">{brokerConfig.static_ip}</div>
          </div>
          <button className="icon-btn" onClick={() => copyToClipboard(brokerConfig.static_ip)}><Copy size={16} /></button>
        </div>
        <div className="info-item">
          <div>
            <div className="info-label">Postback URL</div>
            <div className="info-value url">{brokerConfig.postback_url}</div>
          </div>
          <button className="icon-btn" onClick={() => copyToClipboard(brokerConfig.postback_url)}><Copy size={16} /></button>
        </div>
      </div>

      <style>{`
        .settings-view { padding: 20px; }
        .settings-card { display: flex; flex-direction: column; gap: 16px; background: rgba(255, 255, 255, 0.03); }
        .input-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        .input-group label { display: block; font-size: 12px; margin-bottom: 6px; opacity: 0.7; }
        .info-card { display: flex; flex-direction: column; gap: 20px; }
        .info-item { display: flex; justify-content: space-between; align-items: center; }
        .info-label { font-size: 11px; opacity: 0.5; text-transform: uppercase; letter-spacing: 0.5px; }
        .info-value { font-weight: 600; margin-top: 4px; }
        .info-value.url { font-size: 12px; word-break: break-all; max-width: 250px; }
        .icon-btn { background: transparent; border: none; color: var(--accent); cursor: pointer; padding: 8px; }
      `}</style>
    </div>
  );
};

export default SettingsView;
