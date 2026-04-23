import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { History, LayoutGrid } from 'lucide-react';

const TradesView = () => {
  const [activePositions, setActivePositions] = useState([]);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [resPos, resHist] = await Promise.all([
          axios.get('/api/user/positions'),
          axios.get('/api/user/history')
        ]);
        setActivePositions(resPos.data);
        setHistory(resHist.data);
      } catch (err) {
        console.error(err);
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="trades-view fade-in">
      <div className="section-header">
        <LayoutGrid size={20} className="icon-accent" />
        <h2>Active Positions</h2>
      </div>
      
      <div className="positions-container">
        {activePositions.length > 0 ? (
          activePositions.map((pos) => (
            <div key={pos.symbol} className="m3-card pos-card">
              <div className="pos-main">
                <span className="pos-symbol">{pos.symbol}</span>
                <span className={`pos-pnl ${pos.unrealized >= 0 ? 'up' : 'down'}`}>
                  {pos.unrealized >= 0 ? '+' : ''}{pos.unrealized.toFixed(2)}
                </span>
              </div>
              <div className="pos-details">
                <span>Qty: {pos.qty}</span>
                <span>Avg: ₹{pos.avg_price.toFixed(2)}</span>
              </div>
            </div>
          ))
        ) : (
          <p className="empty-msg">No active positions</p>
        )}
      </div>

      <div className="section-header" style={{ marginTop: '32px' }}>
        <History size={20} className="icon-accent" />
        <h2>Trade History</h2>
      </div>

      <div className="history-list">
        {history.map((t, i) => (
          <div key={i} className="history-item glass">
            <div className="hist-main">
              <span className="hist-symbol">{t.symbol}</span>
              <span className={`hist-type ${t.type}`}>{t.type}</span>
            </div>
            <div className="hist-meta">
              <span>{t.qty} @ ₹{t.price}</span>
              <span>{t.time}</span>
            </div>
          </div>
        ))}
      </div>

      <style>{`
        .trades-view { padding: 20px; }
        .section-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
        .positions-container { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
        .pos-card { background: rgba(255, 255, 255, 0.03); }
        .pos-main { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .pos-symbol { font-weight: 700; font-size: 18px; }
        .pos-pnl { font-weight: 700; font-size: 18px; }
        .pos-pnl.up { color: var(--success); }
        .pos-pnl.down { color: var(--danger); }
        .pos-details { display: flex; justify-content: space-between; font-size: 13px; opacity: 0.6; }
        .history-list { display: flex; flex-direction: column; gap: 12px; }
        .history-item { padding: 16px; border-radius: 16px; border: 1px solid var(--glass-border); }
        .hist-main { display: flex; justify-content: space-between; margin-bottom: 8px; }
        .hist-symbol { font-weight: 600; }
        .hist-type { font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px; text-transform: uppercase; }
        .hist-type.BUY { background: rgba(76, 175, 80, 0.2); color: var(--success); }
        .hist-type.SELL { background: rgba(244, 67, 54, 0.2); color: var(--danger); }
        .hist-meta { display: flex; justify-content: space-between; font-size: 12px; opacity: 0.5; }
        .empty-msg { text-align: center; opacity: 0.5; padding: 40px 0; }
      `}</style>
    </div>
  );
};

export default TradesView;
