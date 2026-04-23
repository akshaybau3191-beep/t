import os
import json
import time
from datetime import datetime, timedelta, date
from backend.models import db, User, AngelConfig, Signal, Trade, Position, DailyStats, SystemStatus, update_system_status

class PythonTradingEngine:
    def __init__(self, app):
        self.app = app
        self.scanned_count = 0
        self.current_task = "Idle"
        # Force absolute path for logs to ensure dashboard sync
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.log_path = os.path.join(self.base_dir, "engine.log")

    def log_to_file(self, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted = f"[{timestamp}] [SCANNER] {message}\n"
        try:
            with open(self.log_path, "a") as f:
                f.write(formatted)
                f.flush() # Ensure it hits disk immediately for dashboard
        except Exception as e:
            print(f"Log Error: {e}")
        print(formatted.strip())

    def is_market_open(self):
        now = datetime.now()
        if now.weekday() > 4: return False
        m_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
        m_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
        return m_start <= now <= m_end

    def scan_market(self, obj):
        """Institutional Deep-Study Loop: Analyzing each candidate individually for CURRENT EXPIRY and +/-200 LTP range"""
        from backend.symbols import SymbolManager
        from backend.strategy import EliteStrategyManager
        
        sm = SymbolManager()
        strategy = EliteStrategyManager(None)
        
        try:
            # 1. Get Nifty Index LTP
            ltp_resp = obj.ltpData("NSE", "NIFTY", "99926000") 
            if not ltp_resp.get('status'): 
                self.log_to_file("[!] Failed to fetch Nifty Index LTP. Check connectivity.")
                return
            nifty_ltp = float(ltp_resp['data']['ltp'])
            
            # 2. Find Candidates in +/- 200 Range (current expiry only)
            candidates = sm.get_options("NIFTY", nifty_ltp, range_pts=200)
            if not candidates:
                self.log_to_file(f"[!] No active NIFTY options found near {nifty_ltp} within ±200 pts")
                return
            
            self.log_to_file(f"🔎 Elite Study: Analyzing {len(candidates)} candidates for current expiry ±200 LTP range...")
            
            for cand in candidates:
                try:
                    # A. Fetch Full Market Data (OI, Volume, Pressure)
                    m_data = obj.getMarketData("FULL", {"NFO": [cand['token']]})
                    if not m_data.get('status') or not m_data.get('data'): continue
                    data = m_data['data']['fetched'][0]
                    
                    # B. Fetch Multi-Timeframe Candles (1m, 3m, 5m) with rate‑limit safety
                    time.sleep(0.2)  # simple rate‑limit guard
                    h1 = obj.getCandleData({
                        "exchange": "NFO", "symboltoken": cand['token'], "interval": "ONE_MINUTE",
                        "fromdate": (datetime.now() - timedelta(minutes=60)).strftime('%Y-%m-%d %H:%M'),
                        "todate": datetime.now().strftime('%Y-%m-%d %H:%M')
                    })
                    
                    time.sleep(0.2)
                    h3 = obj.getCandleData({
                        "exchange": "NFO", "symboltoken": cand['token'], "interval": "THREE_MINUTE",
                        "fromdate": (datetime.now() - timedelta(minutes=180)).strftime('%Y-%m-%d %H:%M'),
                        "todate": datetime.now().strftime('%Y-%m-%d %H:%M')
                    })
                    
                    time.sleep(0.2)
                    h5 = obj.getCandleData({
                        "exchange": "NFO", "symboltoken": cand['token'], "interval": "FIVE_MINUTE",
                        "fromdate": (datetime.now() - timedelta(minutes=300)).strftime('%Y-%m-%d %H:%M'),
                        "todate": datetime.now().strftime('%Y-%m-%d %H:%M')
                    })
                    
                    # C. Run Elite Consensus Analysis
                    analysis = strategy.analyze(
                        cand['symbol'], data, 
                        h1.get('data', []), 
                        h5.get('data', []),
                        candles_3m=h3.get('data', []),
                        logger=self.log_to_file
                    )
                    
                    # D. Process Signal
                    if analysis['status'] in ['BUY', 'STRONG_BUY']:
                        self.log_to_file(f"🔥 ELITE SIGNAL: {cand['symbol']} | Score: {analysis['score']} | {analysis['factors'][0]}")
                        self.broadcast_signal(cand, analysis)
                            
                except Exception as e:
                    print(f"Study error for {cand['symbol']}: {e}")
                    continue
            
            self.scanned_count += 1
            # Heartbeat update handled by worker loop
        except Exception as e:
            self.log_to_file(f"[!] Master Scan Failure: {e}")

    def broadcast_signal(self, cand, analysis):
        with self.app.app_context():
            # Deduplication check (3 mins)
            exists = db.session.query(Signal).filter(
                Signal.token == cand['token'],
                Signal.timestamp > datetime.now() - timedelta(minutes=3)
            ).first()
            
            if not exists:
                new_sig = Signal(
                    index="NIFTY", symbol=cand['symbol'], token=cand['token'],
                    signal_type=cand['type'], confidence=analysis['score'],
                    price=analysis['ltp'], strategy_snapshot=json.dumps(analysis)
                )
                db.session.add(new_sig)
                db.session.commit()
                self.log_to_file(f"📢 MASTER SIGNAL BROADCASTED: {cand['symbol']} at ₹{analysis['ltp']}")

    def execute_for_user(self, user, index, analysis, type, symbol, token):
        from backend.engine import user_sessions
        if user.id not in user_sessions: return
        obj = user_sessions[user.id]
        
        try:
            # Mode Check
            mode = user.config.trading_mode
            if user.expiry_date and user.expiry_date < datetime.now().date(): mode = 'PAPER'
            
            if mode == 'LIVE':
                # LIVE execution logic (Angel One placeOrder)
                self.log_to_file(f"🚀 {user.username} - EXECUTING LIVE TRADE: {symbol}")
                # Actual order placement here
            else:
                self.execute_paper_trade(user, symbol, token, analysis)
        except Exception as e:
            self.log_to_file(f"[!] Execution Error: {e}")

    def execute_paper_trade(self, user, symbol, token, analysis):
        from backend.models import db, Trade
        order_id = f"PAPER-{int(time.time())}"
        self.log_to_file(f"📝 {user.username} - PAPER TRADE: {symbol} at ₹{analysis['ltp']}")
        
        with self.app.app_context():
            new_trade = Trade(
                user_id=user.id, order_id=order_id, symbol=symbol, token=token,
                transaction_type="BUY", quantity=65, price=analysis['ltp'],
                status='COMPLETE', mode='PAPER', strategy_snapshot=json.dumps(analysis)
            )
            db.session.add(new_trade)
            
            mock_data = {
                'orderid': order_id, 'tradingsymbol': symbol, 'symboltoken': token,
                'transactiontype': "BUY", 'quantity': '65', 'averageprice': str(analysis['ltp']),
                'status': 'COMPLETE'
            }
            update_position_from_trade(user.id, mock_data, self.app, mode='PAPER')
            db.session.commit()

def login_angel_one(user, app):
    from SmartApi import SmartConnect
    import pyotp
    try:
        conf = user.config
        if not conf: return False
        obj = SmartConnect(api_key=conf.api_key)
        totp = pyotp.TOTP(conf.totp_secret.replace(" ", "")).now()
        data = obj.generateSession(conf.client_code, conf.password, totp)
        if data['status']:
            from backend.engine import user_sessions
            user_sessions[user.id] = obj
            return True
    except: pass
    return False

def update_position_from_trade(user_id, trade_data, app, mode='PAPER'):
    from backend.models import db, Trade, Position, DailyStats
    with app.app_context():
        order_id = str(trade_data.get('orderid', ''))
        symbol = trade_data.get('tradingsymbol', '')
        token = trade_data.get('symboltoken', '')
        tx_type = trade_data.get('transactiontype', 'BUY')
        qty = int(trade_data.get('quantity', 0))
        price = float(trade_data.get('averageprice', 0))
        
        pos = db.session.query(Position).filter_by(user_id=user_id, token=token).first()
        if not pos:
            pos = Position(user_id=user_id, symbol=symbol, token=token, quantity=0, avg_price=0.0, mode=mode)
            db.session.add(pos)

        if tx_type == 'BUY':
            new_total = pos.quantity + qty
            pos.avg_price = ((pos.avg_price * pos.quantity) + (price * qty)) / new_total if new_total > 0 else 0
            pos.quantity = new_total
        else:
            pos.realized_pnl += qty * (price - pos.avg_price)
            pos.quantity -= qty
            
        db.session.commit()

user_sessions = {}
