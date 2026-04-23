import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Users, CreditCard, Power } from 'lucide-react';

const AdminView = () => {
  const [users, setUsers] = useState([]);
  const [requests, setRequests] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [resUsers, resReqs] = await Promise.all([
          axios.get('/api/admin/users'),
          axios.get('/api/admin/sub_requests')
        ]);
        setUsers(resUsers.data);
        setRequests(resReqs.data);
      } catch (err) {
        console.error(err);
      }
    };
    fetchData();
  }, []);

  const approveSub = async (id) => {
    await axios.post('/api/admin/approve_sub', { id });
    alert('Subscription approved!');
    setRequests(requests.filter(r => r.id !== id));
  };

  const toggleUser = async (user_id) => {
    await axios.post('/api/admin/toggle_user', { user_id });
    alert('User status updated!');
    // Refresh users
    const res = await axios.get('/api/admin/users');
    setUsers(res.data);
  };

  const shutdownServer = async () => {
    if (confirm('Are you sure you want to SHUTDOWN the server?')) {
      await axios.post('/api/shutdown');
    }
  };

  return (
    <div className="admin-view fade-in">
      <div className="section-header">
        <CreditCard size={20} className="icon-accent" />
        <h2>Subscription Requests</h2>
      </div>

      <div className="m3-card table-card">
        <table className="admin-table">
          <thead>
            <tr>
              <th>User</th>
              <th>Reference</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {requests.map((r) => (
              <tr key={r.id}>
                <td>{r.username}</td>
                <td className="ref-cell">{r.upi_ref}</td>
                <td>
                  <button onClick={() => approveSub(r.id)} className="action-btn approve">Approve</button>
                </td>
              </tr>
            ))}
            {requests.length === 0 && <tr><td colSpan="3" style={{ textAlign: 'center', opacity: 0.5, padding: '20px' }}>No pending requests</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="section-header" style={{ marginTop: '32px' }}>
        <Users size={20} className="icon-accent" />
        <h2>User Management</h2>
      </div>

      <div className="m3-card table-card">
        <table className="admin-table">
          <thead>
            <tr>
              <th>User</th>
              <th>Expiry</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.username}</td>
                <td>{u.expiry}</td>
                <td>
                  <button 
                    onClick={() => toggleUser(u.id)} 
                    className={`status-chip ${u.is_active ? 'active' : 'inactive'}`}
                  >
                    {u.is_active ? 'Active' : 'Inactive'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="section-header" style={{ marginTop: '32px' }}>
        <Power size={20} className="icon-accent" />
        <h2>System Controls</h2>
      </div>

      <div className="m3-card settings-card" style={{ display: 'flex', gap: '12px', flexDirection: 'row' }}>
        <button onClick={() => axios.post('/api/admin/kill_switch', { active: true })} className="m3-btn danger" style={{ flex: 1 }}>
          EMERGENCY KILL SWITCH
        </button>
        <button onClick={() => axios.post('/api/admin/reload_config')} className="m3-btn primary" style={{ flex: 1 }}>
          RELOAD CONFIG
        </button>
      </div>

      <div className="danger-zone" style={{ marginTop: '40px' }}>
        <button onClick={shutdownServer} className="m3-btn danger-outline">
          <Power size={18} />
          <span>Shutdown Server</span>
        </button>
      </div>

      <style>{`
        .admin-view { padding: 20px; }
        .table-card { padding: 0; overflow: hidden; background: rgba(255, 255, 255, 0.03); }
        .admin-table { width: 100%; border-collapse: collapse; }
        .admin-table th { text-align: left; padding: 16px; font-size: 12px; opacity: 0.6; border-bottom: 1px solid var(--glass-border); }
        .admin-table td { padding: 16px; border-bottom: 1px solid var(--glass-border); font-size: 14px; }
        .ref-cell { font-family: monospace; font-size: 12px; }
        .action-btn { padding: 6px 12px; border-radius: 6px; border: none; cursor: pointer; font-weight: 600; }
        .action-btn.approve { background: var(--success); color: white; }
        .status-chip { 
          padding: 4px 10px; 
          border-radius: 100px; 
          border: none; 
          font-size: 11px; 
          font-weight: 700; 
          cursor: pointer;
        }
        .status-chip.active { background: rgba(76, 175, 80, 0.2); color: var(--success); }
        .status-chip.inactive { background: rgba(244, 67, 54, 0.2); color: var(--danger); }
        .m3-btn.danger-outline { 
          background: transparent; 
          border: 1px solid var(--danger); 
          color: var(--danger); 
          display: flex; 
          align-items: center; 
          justify-content: center; 
          gap: 12px;
        }
      `}</style>
    </div>
  );
};

export default AdminView;
