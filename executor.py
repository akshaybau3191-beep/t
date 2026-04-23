import time
import json
from datetime import datetime
from backend.models import db, User, Signal, Position
from backend.engine import PythonTradingEngine, user_sessions, login_angel_one
from run import app

def run_executor():
    print("🚀 DISTRIBUTED EXECUTION WORKER STARTING...")
    engine = PythonTradingEngine(app)
    
    while True:
        try:
            with app.app_context():
                # 1. Fetch unprocessed signals
                new_signals = Signal.query.filter_by(is_processed=False).all()
                
                for sig in new_signals:
                    print(f"📡 PROCESSING MASTER SIGNAL: {sig.symbol} (Type: {sig.signal_type})")
                    
                    # 2. Extract analysis from snapshot
                    try:
                        analysis = json.loads(sig.strategy_snapshot)
                    except:
                        print(f"[!] Error decoding snapshot for signal {sig.id}")
                        sig.is_processed = True
                        db.session.commit()
                        continue
                        
                    # 3. Iterate through ALL active users
                    active_users = User.query.filter_by(is_active=True).all()
                    for user in active_users:
                        # Auto-login if needed for execution
                        if user.id not in user_sessions:
                            # We only login users who have config
                            if user.config and user.config.api_key:
                                print(f"[*] Logging in user {user.username} for execution...")
                                login_angel_one(user, app)
                        
                        if user.id in user_sessions:
                            # Execute the trade logic (it already handles roles, subs, and capital)
                            # signal is always 'BUY' for entry in this strategy
                            engine.execute_for_user(user, sig.index, analysis, 'BUY', sig.symbol, sig.token)
                    
                    # 4. Mark as processed
                    sig.is_processed = True
                    db.session.commit()
                    print(f"✅ SIGNAL {sig.id} DISTRIBUTED TO ALL USERS.")
                    
                # 5. Position Monitoring (Check SL/TP for everyone)
                engine.monitor_positions()
                
        except Exception as e:
            print(f"[!] Executor Loop Error: {e}")
            time.sleep(5)
            
        time.sleep(1) # Poll every second for signals

if __name__ == "__main__":
    run_executor()
