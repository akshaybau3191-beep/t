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

    def get_options(self, name, ltp, range_pts=400):
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
            
        # Identify current expiry (Nearest date >= today)
        today = datetime.now()
        def parse_expiry(exp_str):
            try:
                # Format: 25APR2024 or 2024-04-25
                for fmt in ('%d%b%Y', '%Y-%m-%d'):
                    try: return datetime.strptime(exp_str, fmt)
                    except: continue
                return datetime.max
            except: return datetime.max

        unique_expiries = list(set(s.get('expiry') for s in relevant))
        sorted_expiries = sorted(unique_expiries, key=parse_expiry)
        
        # Filter for future/today expiries only
        future_expiries = [e for e in sorted_expiries if parse_expiry(e).date() >= today.date()]
        if not future_expiries:
            return []
            
        current_expiry = future_expiries[0]
        print(f"[*] Identified Current Expiry: {current_expiry}")
        
        # Filter by expiry and strike range
        strike_min = ltp - range_pts
        strike_max = ltp + range_pts
        
        options = []
        for s in relevant:
            if s.get('expiry') == current_expiry:
                try:
                    # Angel One strike handling
                    raw_strike = float(s.get('strike', 0))
                    # Handle both 22400.0 and 2240000.0 formats
                    strike = raw_strike / 100 if raw_strike > 100000 else raw_strike
                        
                    if strike_min <= strike <= strike_max:
                        # Improved CE/PE detection
                        symbol = s.get('symbol', '')
                        opt_type = None
                        if 'CE' in symbol: opt_type = 'CE'
                        elif 'PE' in symbol: opt_type = 'PE'
                        
                        if opt_type:
                            options.append({
                                'symbol': symbol,
                                'token': s.get('token'),
                                'strike': strike,
                                'type': opt_type,
                                'expiry': current_expiry
                            })
                except:
                    continue
        
        # Sort options by strike for better log readability
        options = sorted(options, key=lambda x: x['strike'])
        print(f"[*] Found {len(options)} NIFTY options in +/- 400 range.")
        return options

if __name__ == "__main__":
    sm = SymbolManager()
    if sm.update_master():
        opts = sm.get_options('NIFTY', 22400)
        print(f"Found {len(opts)} options for NIFTY around 22400")
