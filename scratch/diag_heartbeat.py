import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import db, SystemStatus
from run import app
from datetime import datetime

def diag_status():
    with app.app_context():
        stat = SystemStatus.query.first()
        if not stat:
            print("[-] SystemStatus record NOT FOUND in DB.")
            return
        
        print(f"[*] Engine Status: {stat.engine_status}")
        print(f"[*] Engine Task:   {stat.engine_task}")
        print(f"[*] Scanned Count: {stat.scanned_count}")
        print(f"[*] Last Updated:  {stat.last_update}")
        
        now = datetime.now()
        diff = (now - stat.last_update).total_seconds()
        print(f"[*] Time Since Last Heartbeat: {diff:.1f} seconds")
        
        if diff > 60:
            print("[!] Heartbeat is STALE. Worker is likely dead or stuck.")
        else:
            print("[+] Heartbeat is FRESH. If Dashboard is waiting, check your API connection.")

if __name__ == "__main__":
    diag_status()
