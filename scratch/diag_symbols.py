import requests
import json
import os
from datetime import datetime

def diagnostic():
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    print(f"[*] Downloading from {url}")
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            symbols = resp.json()
            print(f"[*] Downloaded {len(symbols)} symbols.")
            
            nifty_syms = [s for s in symbols if s.get('symbol', '').startswith('NIFTY') and s.get('exch_seg') == 'NFO']
            print(f"[*] Total NIFTY NFO Symbols: {len(nifty_syms)}")
            
            if nifty_syms:
                print("[*] Sample Format (First 10):")
                for s in nifty_syms[:10]:
                    print(f"    Symbol: {s.get('symbol')} | Expiry: {s.get('expiry')} | Strike: {s.get('strike')} | Name: {s.get('name')}")
                
                expiries = sorted(list(set([s.get('expiry') for s in nifty_syms if s.get('expiry')])))
                print(f"[*] Available Expiries: {expiries[:5]}")
        else:
            print(f"[-] Failed with status: {resp.status_code}")
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    diagnostic()
