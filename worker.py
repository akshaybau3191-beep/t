import os
import sys
import time
from datetime import datetime, timezone, timedelta

# --- INITIALIZE PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from run import app
from backend.models import db, User, update_system_status, SystemStatus
from backend.engine import PythonTradingEngine, login_angel_one, user_sessions

def run_worker():
    print("[*] AI Trading Worker Process Initializing...")
    try:
        engine = PythonTradingEngine(app)
        engine.log_to_file(">>> WORKER BOOTING: Initializing NIFTY Scanner <<<")
        engine.log_to_file(f"Targeting: NIFTY Only | Range: +/- 400 | Mode: Option Buying")
    except Exception as e:
        print(f"[!] Initialization Failed: {e}")
        return
    
    while True:
        try:
            with app.app_context():
                # 1. Check for Manual Trigger
                stat = SystemStatus.query.first()
                force_scan = False
                if stat and stat.force_scan_trigger:
                    engine.log_to_file("!!! MANUAL SCAN TRIGGERED !!!")
                    stat.force_scan_trigger = False
                    db.session.commit()
                    force_scan = True
                
                # 2. Heartbeat & Status Update
                update_system_status("Worker Running", engine.scanned_count, "Online")
                
                # 3. Market Open Check OR Forced Scan
                if engine.is_market_open() or force_scan:
                    admin = db.session.query(User).filter_by(role='admin').first()
                    if admin:
                        # Auto-login if needed
                        if admin.id not in user_sessions:
                            engine.log_to_file(f"Logging in admin: {admin.username}")
                            login_angel_one(admin, app)
                        
                        if admin.id in user_sessions:
                            # Dedicated Scanning Loop
                            engine.scan_market(user_sessions[admin.id])
                        else:
                            engine.log_to_file("[!] Admin login failed. Cannot scan.")
                    
                    if not force_scan:
                        time.sleep(2) # Faster scanning cycle (Scanner Only)
                    else:
                        engine.log_to_file("Manual Scan Complete.")
                else:
                    # After hours heartbeat
                    if int(time.time()) % 60 == 0:
                        engine.log_to_file("Market closed. Idle Heartbeat...")
                    time.sleep(1) # Fast poll for manual triggers
                    
        except Exception as e:
            print(f"[!] Worker Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_worker()
