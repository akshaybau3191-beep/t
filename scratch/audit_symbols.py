import json
import os
from datetime import datetime

def audit_symbols():
    try:
        path = "/tmp/scrip_master.json"
        if not os.path.exists(path):
            print(f"[-] {path} not found")
            return
            
        with open(path, "r") as f:
            symbols = json.load(f)
            
        nifty_syms = [s for s in symbols if s.get('symbol', '').startswith('NIFTY') and s.get('exch_seg') == 'NFO']
        
        print(f"[*] Total NIFTY NFO Symbols: {len(nifty_syms)}")
        if nifty_syms:
            print("[*] Sample Format (First 10):")
            for s in nifty_syms[:10]:
                print(f"    Symbol: {s.get('symbol')} | Expiry: {s.get('expiry')} | Strike: {s.get('strike')} | Name: {s.get('name')}")
            
            # Find unique expiries
            expiries = sorted(list(set([s.get('expiry') for s in nifty_syms if s.get('expiry')])))
            print(f"[*] Available Expiries: {expiries[:5]}")
            
    except Exception as e:
        print(f"[-] Audit Error: {e}")

if __name__ == "__main__":
    audit_symbols()
