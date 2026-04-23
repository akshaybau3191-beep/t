import os
import sys
import time
import threading
from datetime import datetime, date

# --- VENDORIZED DEPENDENCIES ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from run import app
from backend.models import db, User, update_system_status, SystemStatus
from backend.engine import PythonTradingEngine, login_angel_one, user_sessions

def run_worker():
    print("[*] AI Trading Worker Process Initializing...")
    try:
        engine = PythonTradingEngine(app)
        engine.log_to_file(">>> WORKER BOOTING: Elite Scanner Initialized <<<")
        
        # --- BACKGROUND HEARTBEAT THREAD ---
        def heartbeat_pulse():
            while True:
                try:
                    with app.app_context():
                        update_system_status("Elite Scanner Active", engine.scanned_count, "Online")
                    time.sleep(10) # Pulse every 10 seconds
                except Exception as e:
                    print(f"[!] Heartbeat Pulse Error: {e}")
                    time.sleep(5)
        
        pulse_thread = threading.Thread(target=heartbeat_pulse, daemon=True)
        pulse_thread.start()
        print("[*] Heartbeat Pulse Thread Started.")
        
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
                
                # 2. Market Open Check OR Forced Scan
                if engine.is_market_open() or force_scan:
                    admin = db.session.query(User).filter_by(role='admin').first()
                    if admin:
                        # Auto-login check
                        if admin.id not in user_sessions:
                            engine.log_to_file(f"Logging in admin: {admin.username}")
                            login_angel_one(admin, app)
                        
                        if admin.id in user_sessions:
                            # Dedicated Elite Scanning Loop
                            engine.scan_market(user_sessions[admin.id])
                        else:
                            engine.log_to_file("[!] Admin login failed. Cannot scan.")
                    
                    time.sleep(1) # Fast cycle
                else:
                    time.sleep(5) # Idle mode
                    
        except Exception as e:
            print(f"[!] Worker Loop Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_worker()
