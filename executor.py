import time
import json
import threading
from datetime import datetime
from backend.models import db, User, Signal, Position
from backend.engine import PythonTradingEngine, user_sessions, login_angel_one
from run import app

class UserSupervisor(threading.Thread):
    """
    Dedicated supervisor thread for a single user.
    Handles their signals, monitoring, and risk management.
    """
    def __init__(self, user_id, engine):
        super().__init__()
        self.user_id = user_id
        self.engine = engine
        self.daemon = True
        self.is_running = True
        
    def run(self):
        print(f"👤 Supervisor started for User ID: {self.user_id}")
        last_processed_signal_id = 0
        
        # Pre-fetch last processed signal to avoid double-entry on restart
        with app.app_context():
            latest_sig = Signal.query.order_by(Signal.id.desc()).first()
            if latest_sig:
                last_processed_signal_id = latest_sig.id

        while self.is_running:
            try:
                with app.app_context():
                    user = db.session.get(User, self.user_id)
                    if not user or not user.is_active:
                        print(f"[*] Stopping supervisor for {self.user_id} (User inactive/deleted)")
                        self.is_running = False
                        break
                    
                    # 1. Check for New Signals
                    # Each user thread checks for signals they haven't processed yet
                    new_signals = Signal.query.filter(Signal.id > last_processed_signal_id).all()
                    
                    for sig in new_signals:
                        print(f"🔔 Signal {sig.id} received for {user.username}")
                        try:
                            analysis = json.loads(sig.strategy_snapshot)
                            # Auto-login if needed
                            if user.id not in user_sessions:
                                if user.config and user.config.api_key:
                                    login_angel_one(user, app)
                            
                            if user.id in user_sessions:
                                # Execute (engine handles role/sub/capital checks)
                                self.engine.execute_for_user(user, sig.index, analysis, 'BUY', sig.symbol, sig.token)
                            
                        except Exception as e:
                            print(f"[!] Execution error for {user.username} on signal {sig.id}: {e}")
                        
                        last_processed_signal_id = sig.id
                    
                    # 2. Individual Position Monitoring (SL / TP / Trailing SL)
                    self.engine.monitor_user_positions(user)
                    
            except Exception as e:
                print(f"[!] Supervisor Error for User {self.user_id}: {e}")
            
            time.sleep(1) # Tight monitoring loop

def run_multi_threaded_executor():
    print("🚀 DISTRIBUTED MULTI-THREADED EXECUTOR STARTING...")
    engine = PythonTradingEngine(app)
    supervisors = {}
    
    while True:
        try:
            with app.app_context():
                active_users = User.query.filter_by(is_active=True).all()
                active_user_ids = {u.id for u in active_users}
                
                # 1. Start supervisors for new users
                for user_id in active_user_ids:
                    if user_id not in supervisors or not supervisors[user_id].is_alive():
                        supervisor = UserSupervisor(user_id, engine)
                        supervisor.start()
                        supervisors[user_id] = supervisor
                
                # 2. Cleanup inactive supervisors
                current_ids = list(supervisors.keys())
                for uid in current_ids:
                    if uid not in active_user_ids:
                        supervisors[uid].is_running = False
                        del supervisors[uid]
                        
        except Exception as e:
            print(f"[!] Master Executor Error: {e}")
            
        time.sleep(10) # Refresh user list every 10s

if __name__ == "__main__":
    run_multi_threaded_executor()
