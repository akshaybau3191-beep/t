import os
import json
import time
from datetime import datetime, timedelta, date
from backend.models import db, User, AngelConfig, Signal, Trade, Position, DailyStats, SystemStatus

class PythonTradingEngine:
    def __init__(self, app):
        self.app = app
        self.scanned_count = 0
        self.current_task = "Idle"
        self.log_path = "engine.log"

    def log_to_file(self, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted = f"[{timestamp}] [SCANNER] {message}\n"
        with open(self.log_path, "a") as f:
            f.write(formatted)
        print(formatted.strip())

    def is_market_open(self):
        now = datetime.now()
        # Monday to Friday, 9:15 AM to 3:30 PM
        if now.weekday() > 4: return False
        market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
        return market_start <= now <= market_end

    def scan_market(self, obj):
        """Elite Multi-Factor Scanning Loop: Individual Candidate Study"""
        from backend.symbols import SymbolManager
        from backend.strategy import EliteStrategyManager
        
        sm = SymbolManager()
        strategy = EliteStrategyManager(None)
        
        try:
            # 1. Get Nifty LTP
            ltp_resp = obj.ltpData("NSE", "NIFTY", "99926000") 
            if not ltp_resp.get('status'): return
            nifty_ltp = float(ltp_resp['data']['ltp'])
            
            # 2. Find +/- 400 Candidates
            candidates = sm.get_options("NIFTY", nifty_ltp, range_pts=400)
            if not candidates:
                self.log_to_file(f"[!] No active NIFTY options found in +/- 400 range")
                return
            
            self.log_to_file(f"🔎 Studying {len(candidates)} candidates individually...")
            
            for cand in candidates:
                try:
                    # A. Fetch Full Market Data (OI, Volume, Orderbook)
                    market_data = obj.getMarketData("FULL", {"NFO": [cand['token']]})
                    if not market_data.get('status') or not market_data['data']: continue
                    data = market_data['data']['fetched'][0]
                    
                    # B. Fetch Historical Data (1m and 5m)
                    time.sleep(0.35) # Rate limit pacer
                    hist_1m = obj.getCandleData({
                        "exchange": "NFO", "symboltoken": cand['token'],
                        "interval": "ONE_MINUTE",
                        "fromdate": (datetime.now() - timedelta(minutes=60)).strftime('%Y-%m-%d %H:%M'),
                        "todate": datetime.now().strftime('%Y-%m-%d %H:%M')
                    })
                    
                    time.sleep(0.35)
                    hist_5m = obj.getCandleData({
                        "exchange": "NFO", "symboltoken": cand['token'],
                        "interval": "FIVE_MINUTE",
                        "fromdate": (datetime.now() - timedelta(minutes=200)).strftime('%Y-%m-%d %H:%M'),
                        "todate": datetime.now().strftime('%Y-%m-%d %H:%M')
                    })
                    
                    # C. Elite Quantitative Analysis
                    analysis = strategy.analyze(
                        cand['symbol'], data, 
                        hist_1m.get('data', []), 
                        hist_5m.get('data', []),
                        logger=self.log_to_file
                    )
                    
                    # D. Broadcast Signal if High Confidence Score Found
                    if analysis['status'] in ['BUY', 'STRONG_BUY']:
                        self.log_to_file(f"🔥 ELITE SIGNAL: {cand['symbol']} | Score: {analysis['score']} | Verdict: {analysis['status']}")
                        with self.app.app_context():
                            exists = db.session.query(Signal).filter(
                                Signal.token == cand['token'],
                                Signal.timestamp > datetime.now() - timedelta(minutes=3)
                            ).first()
                            
                            if not exists:
                                new_sig = Signal(
                                    index="NIFTY",
                                    symbol=cand['symbol'],
                                    token=cand['token'],
                                    type=cand['type'],
                                    score=analysis['score'],
                                    strategy_snapshot=json.dumps(analysis)
                                )
                                db.session.add(new_sig)
                                db.session.commit()
                            
                except Exception as e:
                    print(f"[!] Study Error for {cand['symbol']}: {e}")
                    continue
                    
            self.scanned_count += 1
        except Exception as e:
            self.log_to_file(f"[!] Master Scan Error: {e}")

    def execute_for_user(self, user, index, analysis, type, symbol, token):
        """Dedicated Execution Logic for a Single User"""
        from backend.engine import user_sessions
        if user.id not in user_sessions: return
        obj = user_sessions[user.id]
        
        try:
            # 1. Risk Check
            if not self.check_user_risk(user):
                self.log_to_file(f"⚠️ {user.username} - RISK LIMIT HIT. Trading Stopped.")
                return

            # 2. Capital Check & Lot Calculation
            from backend.risk import RiskManager
            rm = RiskManager()
            lots = rm.calculate_lots(user, analysis['ltp'])
            
            if lots <= 0:
                self.log_to_file(f"⚠️ {user.username} - Insufficient Capital for 1 Lot. (PAPER MODE)")
                self.execute_paper_trade(user, symbol, token, analysis)
                return

            # 3. Check Role & Subscription
            mode = user.config.trading_mode
            if user.role == 'admin': mode = 'PAPER'
            
            if user.expiry_date and user.expiry_date < datetime.now().date():
                self.log_to_file(f"⚠️ {user.username} - Subscription Expired. (PAPER MODE)")
                mode = 'PAPER'
            
            # 4. Final Execution
            if mode == 'LIVE':
                qty = int(lots * 65) if "NIFTY" in symbol else int(lots * 30)
                self.log_to_file(f"🚀 {user.username} - PLACING LIVE ORDER: {symbol} | Qty: {qty}")
                obj.placeOrder({
                    "variety": "NORMAL", "tradingsymbol": symbol, "symboltoken": token,
                    "transactiontype": type, "exchange": "NFO", "ordertype": "MARKET",
                    "producttype": "CARRYOVER", "duration": "DAY", "quantity": qty
                })
            else:
                self.execute_paper_trade(user, symbol, token, analysis)
                
        except Exception as e:
            self.log_to_file(f"[!] Execution Error for {user.username}: {e}")

    def execute_paper_trade(self, user, symbol, token, analysis):
        """Mock execution for testing and non-subscribers"""
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

    def monitor_user_positions(self, user):
        from backend.engine import user_sessions
        if user.id not in user_sessions: return
        obj = user_sessions[user.id]
        
        with self.app.app_context():
            positions = db.session.query(Position).filter(Position.user_id == user.id, Position.quantity != 0).all()
            for pos in positions:
                try:
                    ltp_resp = obj.ltpData("NFO", pos.symbol, pos.token)
                    if ltp_resp.get('status') and ltp_resp.get('data'):
                        ltp = float(ltp_resp['data']['ltp'])
                        pos.last_price = ltp
                        pos.unrealized_pnl = pos.quantity * (ltp - pos.avg_price)
                        
                        # Trailing SL Logic
                        profit_pct = (pos.unrealized_pnl / (abs(pos.quantity) * pos.avg_price)) * 100
                        if profit_pct > 1.0:
                            trail_buffer = pos.avg_price * (user.config.trailing_sl_pct / 100)
                            new_tsl = ltp - trail_buffer
                            if not pos.tsl_price or new_tsl > pos.tsl_price:
                                pos.tsl_price = new_tsl

                        # Exit Check
                        exit_triggered = False
                        if pos.tp_price and ltp >= pos.tp_price: exit_triggered = True
                        effective_sl = pos.tsl_price or pos.sl_price
                        if effective_sl and ltp <= effective_sl: exit_triggered = True
                        
                        if exit_triggered:
                            self.exit_position(user, pos, ltp)
                    db.session.commit()
                except Exception as e:
                    print(f"[!] Monitor Error: {e}")

    def exit_position(self, user, pos, ltp):
        self.log_to_file(f"🛡️ EXIT: {user.username} - {pos.symbol} at {ltp}")
        mock_exit = {
            'orderid': f'EXIT-{int(time.time())}', 'tradingsymbol': pos.symbol,
            'symboltoken': pos.token, 'transactiontype': 'SELL' if pos.quantity > 0 else 'BUY',
            'quantity': str(abs(pos.quantity)), 'averageprice': str(ltp), 'status': 'COMPLETE'
        }
        update_position_from_trade(user.id, mock_exit, self.app, mode=pos.mode)

    def check_user_risk(self, user):
        from backend.risk import RiskManager
        rm = RiskManager()
        stats_db = db.session.query(DailyStats).filter_by(user_id=user.id, date=date.today()).first()
        current_stats = {
            'daily_pnl': stats_db.total_pnl if stats_db else 0.0,
            'trades_count': stats_db.trades_count if stats_db else 0
        }
        return rm.can_trade(user.config, current_stats)

def login_angel_one(user, app):
    from SmartApi import SmartConnect
    import pyotp
    try:
        conf = user.config
        if not conf or not conf.api_key:
            print(f"[!] {user.username} has no AngelConfig.")
            return False
        obj = SmartConnect(api_key=conf.api_key)
        totp = pyotp.TOTP(conf.totp_secret.replace(" ", "")).now()
        data = obj.generateSession(conf.client_code, conf.password, totp)
        if data['status']:
            from backend.engine import user_sessions
            user_sessions[user.id] = obj
            print(f"[*] {user.username} Login Successful!")
            return True
        else:
            print(f"[!] {user.username} Login Failed: {data.get('message')}")
    except Exception as e:
        print(f"[!] {user.username} Login Error: {e}")
    return False

def update_position_from_trade(user_id, trade_data, app, mode='PAPER'):
    from backend.models import db, Trade, Position, DailyStats
    with app.app_context():
        order_id = str(trade_data.get('orderid', trade_data.get('order_id', '')))
        symbol = trade_data.get('tradingsymbol', trade_data.get('symbol'))
        token = trade_data.get('symboltoken', trade_data.get('token'))
        tx_type = trade_data.get('transactiontype', trade_data.get('transaction_type'))
        qty = int(trade_data.get('quantity', trade_data.get('fillqty', 0)))
        price = float(trade_data.get('averageprice', trade_data.get('fillprice', trade_data.get('price', 0))))
        
        trade = db.session.query(Trade).filter_by(order_id=order_id).first()
        if not trade:
            trade = Trade(user_id=user_id, order_id=order_id, symbol=symbol, token=token,
                          transaction_type=tx_type, quantity=qty, price=price, status='COMPLETE', mode=mode)
            db.session.add(trade)
        
        pos = db.session.query(Position).filter_by(user_id=user_id, token=token).first()
        if not pos:
            pos = Position(user_id=user_id, symbol=symbol, token=token, quantity=0, avg_price=0.0, mode=mode)
            db.session.add(pos)

        if tx_type == 'BUY':
            if pos.quantity < 0:
                closed_qty = min(abs(pos.quantity), qty)
                pos.realized_pnl += closed_qty * (pos.avg_price - price)
                pos.quantity += qty
            else:
                new_total = (pos.quantity or 0) + qty
                pos.avg_price = (((pos.avg_price or 0.0) * (pos.quantity or 0)) + (price * qty)) / new_total
                pos.quantity = new_total
        else:
            if pos.quantity > 0:
                closed_qty = min(pos.quantity, qty)
                pos.realized_pnl += closed_qty * (price - pos.avg_price)
                pos.quantity -= qty
            else:
                new_total = abs(pos.quantity or 0) + qty
                pos.avg_price = (((pos.avg_price or 0.0) * abs(pos.quantity or 0)) + (price * qty)) / new_total
                pos.quantity -= qty

        stats = db.session.query(DailyStats).filter_by(user_id=user_id, date=date.today()).first()
        if not stats:
            stats = DailyStats(user_id=user_id, date=date.today())
            db.session.add(stats)
        stats.total_pnl = db.session.query(db.func.sum(Position.realized_pnl)).filter_by(user_id=user_id).scalar() or 0.0
        stats.trades_count += 1
        db.session.commit()

user_sessions = {}
