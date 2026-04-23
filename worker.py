import os
import sys
import time
import threading
from datetime import datetime

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
        engine.log_to_file(">>> WORKER BOOTING: Institutional Elite Engine Ready <<<")
    except Exception as e:
        print(f"[!] Initialization Failed: {e}")
        return
    
    while True:
        try:
            with app.app_context():
                # 1. Update Heartbeat First (Priority)
                update_system_status("Elite Scanner Active", engine.scanned_count, "Online")
                
                # 2. Check for Manual Trigger
                stat = SystemStatus.query.first()
                force_scan = False
                if stat and stat.force_scan_trigger:
                    engine.log_to_file("!!! MANUAL SCAN TRIGGERED !!!")
                    stat.force_scan_trigger = False
                    db.session.commit()
                    force_scan = True
                
                # 3. Market Open Check OR Forced Scan
                if engine.is_market_open() or force_scan:
                    admin = db.session.query(User).filter_by(role='admin').first()
                    if admin:
                        # Auto-login check (Essential for 24/7 stability)
                        if admin.id not in user_sessions:
                            engine.log_to_file(f"Authenticating admin: {admin.username}")
                            login_angel_one(admin, app)
                        
                        if admin.id in user_sessions:
                            # Start Deep Study Cycle
                            engine.scan_market(user_sessions[admin.id])
                        else:
                            engine.log_to_file("[!] Admin Login Missing. Please check Settings.")
                    
                    time.sleep(2) # Optimized scanning cycle
                else:
                    # Idle Mode logging (Low frequency)
                    if int(time.time()) % 600 == 0:
                        engine.log_to_file("Market closed. Scanner in standby mode.")
                    time.sleep(5)
                    
        except Exception as e:
            print(f"[!] Worker Loop Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_worker()
