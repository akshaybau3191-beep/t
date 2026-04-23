import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import db, User, AngelConfig
from run import app

def check_config():
    with app.app_context():
        admin = User.query.filter_by(role='admin').first()
        if not admin:
            print("[-] Admin user not found.")
            return
        
        print(f"[*] Admin User: {admin.username} (ID: {admin.id})")
        
        config = AngelConfig.query.filter_by(user_id=admin.id).first()
        if config:
            print("[+] AngelConfig Found!")
            print(f"    Client Code: {config.client_code}")
            print(f"    API Key: {config.api_key[:5]}*****")
        else:
            print("[-] No AngelConfig found for admin. PLEASE CONFIGURE IN DASHBOARD.")

if __name__ == "__main__":
    check_config()
