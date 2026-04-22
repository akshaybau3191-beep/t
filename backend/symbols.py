import requests
import json
import os
import time
from datetime import datetime, timedelta

class SymbolManager:
    def __init__(self, cache_dir='/tmp'):
        self.cache_path = os.path.join(cache_dir, 'scrip_master.json')
        self.url = "https://margincalculator.angelbroking.com/OpenAPI_Standard/v1/OpenAPIScripMaster.json"
        self.symbols = []
        self.last_update = 0
        
    def update_master(self):
        # Cache for 24 hours
        if os.path.exists(self.cache_path):
            mtime = os.path.getmtime(self.cache_path)
            if time.time() - mtime < 86400:
                with open(self.cache_path, 'r') as f:
                    self.symbols = json.load(f)
                return True
        
        try:
            print("[*] Downloading Angel One Scrip Master...")
            resp = requests.get(self.url, timeout=30)
            if resp.status_code == 200:
                self.symbols = resp.json()
                with open(self.cache_path, 'w') as f:
                    json.dump(self.symbols, f)
                print(f"[*] Downloaded {len(self.symbols)} symbols.")
                return True
        except Exception as e:
            print(f"[!] Error downloading scrip master: {e}")
        return False

    def get_options(self, name, ltp, range_pts=500):
        if not self.symbols:
            self.update_master()
            
        # Filter for NIFTY/BANKNIFTY options in NFO
        # Name in scrip master for options is usually 'NIFTY' or 'BANKNIFTY'
        # with 'exch_seg': 'NFO' and 'instrumenttype': 'OPTIDX'
        
        relevant = [
            s for s in self.symbols 
            if s.get('name') == name 
            and s.get('exch_seg') == 'NFO' 
            and s.get('instrumenttype') == 'OPTIDX'
        ]
        
        if not relevant:
            return []
            
        # Identify current expiry
        # Format usually: 25APR24 (Weekly/Monthly)
        # We need to find the nearest expiry date
        expiries = sorted(list(set(s.get('expiry') for s in relevant)))
        if not expiries:
            return []
            
        # For simplicity, assume the first expiry is the current one
        # In production, we'd compare with today's date
        current_expiry = expiries[0]
        
        # Filter by expiry and strike range
        strike_min = ltp - range_pts
        strike_max = ltp + range_pts
        
        options = []
        for s in relevant:
            if s.get('expiry') == current_expiry:
                try:
                    strike = float(s.get('strike', 0)) / 100 # Angel One often uses strike * 100
                    if strike == 0: # Some use normal strike
                        strike = float(s.get('strike', 0))
                        
                    if strike_min <= strike <= strike_max:
                        options.append({
                            'symbol': s.get('symbol'),
                            'token': s.get('token'),
                            'strike': strike,
                            'type': 'CE' if s.get('symbol').endswith('CE') else 'PE',
                            'expiry': current_expiry
                        })
                except:
                    continue
        
        return options

if __name__ == "__main__":
    sm = SymbolManager()
    if sm.update_master():
        opts = sm.get_options('NIFTY', 22400)
        print(f"Found {len(opts)} options for NIFTY around 22400")
