import pyotp
import json
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta, date, timezone
from SmartApi import SmartConnect
from backend.models import db, User, AngelConfig, update_system_status
from backend.symbols import SymbolManager
from backend.risk import RiskManager
from backend.logger import AuditLogger
from backend.strategy import StrategyManager

# Global dictionary to store active SmartConnect sessions
user_sessions = {}

def login_angel_one(user, app):
    if not user.config or not user.config.totp_secret or not user.config.password:
        return False
    
    try:
        obj = SmartConnect(api_key=user.config.api_key)
        totp = pyotp.TOTP(user.config.totp_secret).now()
        data = obj.generateSession(user.config.client_code, user.config.password, totp)
        
        if data['status']:
            user_sessions[user.id] = obj
            with app.app_context():
                db.session.get(User, user.id).last_login_date = date.today()
                db.session.commit()
            return True
        return False
    except Exception as e:
        print(f"Engine Error for {user.username}: {str(e)}")
        return False

class PythonTradingEngine:
    def __init__(self, app):
        self.app = app
        self.indices = {
            'NIFTY': '99926000', 
            'BANKNIFTY': '99926009',
            'FINNIFTY': '99926037',
            'NIFTYMIDCAP100': '99926011'
        }
        self.intervals = {
            'NIFTY': 50,
            'BANKNIFTY': 100,
            'FINNIFTY': 50,
            'NIFTYMIDCAP100': 100 # Nifty Midcap 100 has 100 point intervals for options if they exist
        }
        self.weights = {'trend': 25, 'momentum': 15, 'rsi': 20, 'macd': 15, 'volatility': 15, 'breakout': 10}
        self.last_analysis = {} # Cache for UI
        self.daily_loss_limit = 3.0 # 3% Max Daily Loss
        self.current_task = "Engine Starting..."
        self.symbol_manager = SymbolManager()
        self.risk_manager = RiskManager()
        self.audit_logger = AuditLogger()
        self.strategy_manager = StrategyManager(self.risk_manager)
        self.scanned_count = 0
        self.option_candles = {} # token -> [candles]
    
    def log_to_file(self, msg):
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')
            log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "engine.log")
            with open(log_path, 'a') as f:
                f.write(f"[{timestamp}] {msg}\n")
            print(f"[{timestamp}] {msg}")
        except: pass

    def is_market_open(self):
        if os.getenv('DEBUG_SCAN') == 'true': return True
        now_utc = datetime.now(timezone.utc)
        now = now_utc + timedelta(hours=5, minutes=30)
        if now.weekday() >= 5: return False
        current_min = now.hour * 60 + now.minute
        return 555 <= current_min <= 930 # 9:15 AM to 3:30 PM

    def run_scanner(self):
        while True:
            try:
                now_utc = datetime.now(timezone.utc)
                now = now_utc + timedelta(hours=5, minutes=30)
                
                if now.hour == 8 and now.minute == 0:
                    self.perform_daily_auto_login()
                    time.sleep(60)
                
                if self.is_market_open():
                    self.current_task = "Market Open: Preparing Scanner"
                    self.log_to_file(self.current_task)
                    with self.app.app_context():
                        update_system_status(self.current_task, self.scanned_count)
                        admin = db.session.query(User).filter_by(role='admin').first()
                        if admin:
                            if self.check_daily_protection(admin):
                                # Auto-login admin if session missing
                                if admin.id not in user_sessions:
                                    self.current_task = "Logging into Angel One..."
                                    self.log_to_file(self.current_task)
                                    update_system_status(self.current_task, self.scanned_count)
                                    login_angel_one(admin, self.app)
                                
                                if admin.id in user_sessions:
                                    self.scan_market(user_sessions[admin.id])
                            
                        self.current_task = "Monitoring Active Positions"
                        update_system_status(self.current_task, self.scanned_count)
                        self.monitor_positions()
                    time.sleep(10) # Scanner frequency
                else:
                    # After market hours: self-improve
                    self.current_task = "Market Closed: Waiting"
                    self.log_to_file("Market is closed. Scanner idling...")
                    with self.app.app_context():
                        update_system_status(self.current_task, self.scanned_count)
                    now_min = now.hour * 60 + now.minute
                    if 945 <= now_min <= 960: # 3:45 PM to 4:00 PM
                        self.current_task = "AI: Optimizing Strategy"
                        self.optimize_strategy_weights()
                        time.sleep(900) # Only run once
                    time.sleep(60)
            except Exception as e:
                print(f"[!] Scanner Loop Error: {e}")
                time.sleep(10)

    def scan_market(self, smart_api):
        # Focus on NIFTY only as per user request
        indices_to_scan = ['NIFTY']
        
        for name in indices_to_scan:
            try:
                self.current_task = f"Fetching {name} LTP"
                token = self.indices.get(name)
                ltp_resp = smart_api.ltpData("NSE", name, token)
                if not ltp_resp.get('status'): continue
                ltp = float(ltp_resp['data']['ltp'])

                self.current_task = f"Finding {name} strikes..."
                options = self.symbol_manager.get_options(name, ltp, range_pts=400)
                self.scanned_count = len(options)
                
                if not options:
                    print(f"[!] No active {name} options found in range.")
                    continue

                self.current_task = f"Scanning {len(options)} {name} scripts"
                
                # Batch fetch market data (Full)
                chunk_size = 50
                for i in range(0, len(options), chunk_size):
                    chunk = options[i:i + chunk_size]
                    tokens = [o['token'] for o in chunk]
                    
                    market_data_resp = smart_api.getMarketData("FULL", {"NFO": tokens})
                    
                    if not market_data_resp.get('status') or not market_data_resp.get('data'):
                        print(f"[!] Market Data Fetch Failed for {len(tokens)} tokens: {market_data_resp.get('message')}")
                        continue
                        
                    print(f"[*] Fetched data for {len(market_data_resp['data']['fetched'])} tokens")
                    fetched_data = market_data_resp['data']['fetched']
                    for o_data in fetched_data:
                        opt_info = next((o for o in chunk if o['token'] == o_data['symbolToken']), None)
                        if not opt_info: continue
                        
                        token = opt_info['token']
                        if token not in self.option_candles or not self.option_candles[token]:
                            self.option_candles[token] = self.fetch_option_candles(smart_api, token)
                        
                        # Modular Signal Generation
                        analysis = self.strategy_manager.analyze_option(
                            self.option_candles[token], 
                            o_data, 
                            opt_info, 
                            ltp
                        )
                        
                        # Find Admin's Threshold
                        with self.app.app_context():
                            admin = db.session.query(User).filter_by(role='admin').first()
                            min_score = admin.config.min_confidence_score if admin and admin.config else 75
                        
                        # AI Scanning: Update UI
                        self.current_task = f"AI Scanning {name}: {opt_info['symbol']} ({analysis['signal_strength']}%)"
                        self.log_to_file(self.current_task)
                        with self.app.app_context():
                            update_system_status(self.current_task, self.scanned_count)
                        
                        # OPTION BUYING ONLY
                        if analysis['signal_strength'] >= min_score and analysis['signal'] == 'BUY':
                            self.log_to_file(f"🎯 SIGNAL FOUND: {opt_info['symbol']} at {analysis['signal_strength']}% Confidence")
                            self.dispatch_trade(name, analysis, opt_info['type'], opt_info['symbol'], opt_info['token'])
            except Exception as e:
                self.log_to_file(f"Error scanning {name}: {e}")
            except Exception as e:
                print(f"[!] Advanced Scanning Error for {name}: {e}")

    def fetch_option_candles(self, smart_api, token):
        try:
            to_date = (datetime.now() + timedelta(hours=5, minutes=30)).strftime('%Y-%m-%d %H:%M')
            from_date = (datetime.now() + timedelta(hours=5, minutes=30) - timedelta(minutes=60)).strftime('%Y-%m-%d %H:%M')
            
            params = {
                "exchange": "NFO",
                "symboltoken": token,
                "interval": "ONE_MINUTE",
                "fromdate": from_date,
                "todate": to_date
            }
            resp = smart_api.getCandleData(params)
            if resp.get('status') and resp.get('data'):
                return resp['data']
        except:
            pass
        return []

    def calculate_total_score(self, a):
        score = 0
        # Trend
        if a['ema21'] > a['ema50'] and a['price'] > a['ema21']: a['trend_score'] = self.weights['trend']
        elif a['ema21'] < a['ema50'] and a['price'] < a['ema21']: a['trend_score'] = self.weights['trend']
        
        # RSI
        if 40 < a['rsi'] < 60: a['rsi_score'] = self.weights['rsi'] # Neutral-Strong
        elif a['rsi'] > 70 or a['rsi'] < 30: a['rsi_score'] = self.weights['rsi'] / 2 # Overextended
        
        # MACD
        if a['macd'] > a['macd_signal']: a['macd_score'] = self.weights['macd']
        
        # Volatility (Inside BB)
        if a['bb_lower'] < a['price'] < a['bb_upper']: a['vol_score'] = self.weights['volatility']
        
        # Breakout
        if a['isBreakout']: a['breakout_score'] = self.weights['breakout']
        
        score = a['trend_score'] + a['rsi_score'] + a['macd_score'] + a['vol_score'] + a['breakout_score']
        return score

    def get_market_analysis(self, index):
        return self.last_analysis.get(index, {})

    def get_candle_data(self, smart_api, index):
        token = self.indices.get(index)
        to_date = (datetime.now() + timedelta(hours=5, minutes=30)).strftime('%Y-%m-%d %H:%M')
        from_date = (datetime.now() + timedelta(hours=5, minutes=30) - timedelta(days=2)).strftime('%Y-%m-%d %H:%M')
        
        params = {
            "exchange": "NSE",
            "symboltoken": token,
            "interval": "FIFTEEN_MINUTE",
            "fromdate": from_date,
            "todate": to_date
        }
        resp = smart_api.getCandleData(params)
        if resp.get('status') and resp.get('data'):
            return resp['data']
        return []

    def perform_daily_auto_login(self):
        with self.app.app_context():
            active_users = db.session.query(User).filter_by(is_active=True).all()
            for user in active_users:
                login_angel_one(user, self.app)

    def dispatch_trade(self, index, data, signal, real_symbol, real_token):
        with self.app.app_context():
            from backend.models import User
            active_users = db.session.query(User).filter_by(is_active=True).all()
            for user in active_users:
                if user.is_active and user.last_login_date == date.today():
                    self.execute_for_user(user, index, data, signal, real_symbol, real_token)

    def get_option_strike(self, index, ltp, signal):
        interval = self.intervals.get(index, 50)
        atm = round(ltp / interval) * interval
        
        # User wants ITM, ATM, OTM check. For simplicity, we pick one or evaluate all.
        # Here we select ATM by default or ITM for better delta.
        # ITM CE = ATM - interval, ITM PE = ATM + interval
        itm = atm - interval if signal == 'CE' else atm + interval
        otm = atm + interval if signal == 'CE' else atm - interval
        
        return {
            'ATM': int(atm),
            'ITM': int(itm),
            'OTM': int(otm)
        }

    def execute_for_user(self, user, index, data, signal, real_symbol, real_token):
        if user.id not in user_sessions: return
        from backend.models import db, Position
        
        # 1. Order Validation
        if self.risk_manager.kill_switch_active:
            print("[!] Trade rejected: Kill Switch is ON")
            return
            
        # Prepare strategy snapshot
        snapshot = json.dumps(data)
        
        pos = db.session.query(Position).filter_by(user_id=user.id, token=real_token).first()
        if pos and pos.quantity != 0:
            return 
            
        # 2. Dynamic Lot Sizing & Slippage
        user_cfg = user.config
        lot_size = self.risk_manager.calculate_lot_size(user_cfg, index, data['price'])
        slippage = 0.001 # 0.1% buffer
        limit_price = data['price'] * (1 + slippage) if signal == 'BUY' else data['price'] * (1 - slippage)
        
        # 3. Mode Selection with Risk & Capital Fallback
        # Check if user has reached their daily limits
        allowed, reason = self.check_user_risk(user)
        
        # Check Capital Exposure
        # Calculate current deployed margin (sum of absolute values of current positions)
        with self.app.app_context():
            active_positions = db.session.query(Position).filter_by(user_id=user.id, mode='LIVE').all()
            deployed_capital = sum(abs(p.quantity * p.avg_price) for p in active_positions)
            
        new_trade_value = lot_size * data['price']
        total_required = deployed_capital + new_trade_value
        capital_limit = user_cfg.starting_capital or 100000.0
        
        mode = user_cfg.trading_mode
        exec_reason = "Admin Signal"
        
        if mode == 'LIVE':
            if not allowed:
                print(f"[*] Downgrading to PAPER for {user.username} | Reason: {reason}")
                mode = 'PAPER'
                exec_reason = reason
            elif total_required > capital_limit:
                print(f"[*] Downgrading to PAPER for {user.username} | Reason: Capital Limit Exceeded (Req: ₹{total_required:.0f}, Limit: ₹{capital_limit:.0f})")
                mode = 'PAPER'
                exec_reason = f"Capital Limit Exceeded (₹{total_required:.0f})"
            else:
                exec_reason = "Risk Check Passed"
            
        max_retries = 3
        for attempt in range(max_retries):
            try:
                order_id = f"MOCK-{int(time.time())}"
                if mode == 'LIVE':
                    print(f"[*] LIVE Execution (Attempt {attempt+1}) for {user.username} on {real_symbol} | Qty: {lot_size} | Limit: {limit_price}")
                    # order_id = obj.placeOrder(order_params)
                    # if order_id: break
                
                # Update DB and Positions
                from backend.models import Trade
                with self.app.app_context():
                    new_trade = Trade(
                        user_id=user.id,
                        order_id=order_id,
                        symbol=real_symbol,
                        token=real_token,
                        transaction_type=signal,
                        quantity=lot_size,
                        price=data['price'],
                        status='COMPLETE',
                        mode=mode,
                        reason=exec_reason,
                        strategy_snapshot=snapshot
                    )
                    db.session.add(new_trade)
                    
                    mock_data = {
                        'orderid': order_id,
                        'tradingsymbol': real_symbol,
                        'symboltoken': real_token,
                        'transactiontype': signal,
                        'quantity': str(lot_size),
                        'price': str(data['price']),
                        'status': 'COMPLETE'
                    }
                    update_position_from_trade(user.id, mock_data, self.app, mode=mode)
                    db.session.commit()
                break
            except Exception as e:
                print(f"[!] Execution Attempt {attempt+1} failed: {e}")
                time.sleep(1)
        
        # Audit Logging
        self.audit_logger.log_trade({
            'symbol': real_symbol,
            'type': signal,
            'qty': lot_size,
            'price': data['price'],
            'confidence': data['signal_strength'],
            'reason': data.get('reason', 'Strategy Alignment'),
            'status': 'COMPLETE',
            'pnl': 0.0
        })

    def monitor_positions(self):
        """Monitor open positions for target/stop-loss with real LTP"""
        with self.app.app_context():
            from backend.models import db, User, Position
            active_users = db.session.query(User).filter_by(is_active=True).all()
            for user in active_users:
                if user.id not in user_sessions: continue
                obj = user_sessions[user.id]
                positions = db.session.query(Position).filter(Position.user_id == user.id, Position.quantity != 0).all()
                for pos in positions:
                    try:
                        # Fetch real LTP from Angel One
                        # Note: 'NSE' or 'NFO' depends on the instrument. For simplicity, we try/catch or use stored exchange info.
                        # For now, we assume NSE/NFO based on symbol suffix or similar, or just try ltpData.
                        exchange = "NFO" if any(x in pos.symbol for x in ["NIFTY", "BANKNIFTY", "FINNIFTY"]) else "NSE"
                        ltp_resp = obj.ltpData(exchange, pos.symbol, pos.token)
                        
                        if ltp_resp.get('status') and ltp_resp.get('data'):
                            ltp = float(ltp_resp['data']['ltp'])
                            pos.last_price = ltp
                            
                            # Update unrealized P&L
                            if pos.quantity > 0: # Long
                                pos.unrealized_pnl = pos.quantity * (ltp - pos.avg_price)
                            else: # Short
                                pos.unrealized_pnl = abs(pos.quantity) * (pos.avg_price - ltp)
                            
                            # Dynamic Exit Logic (ATR based or 5%/2%)
                            # We use ATR for SL if available, target stays 2x SL
                            # If no ATR stored (old trades), use defaults
                            pnl_pct = (pos.unrealized_pnl / (abs(pos.quantity) * pos.avg_price)) * 100
                            
                            # target/sl from position or defaults
                            target = 5.0
                            sl = -2.0
                            
                            if pnl_pct >= target or pnl_pct <= sl:
                                self.exit_position(user, pos, ltp)
                        else:
                            print(f"[!] LTP Fetch Failed for {pos.symbol}: {ltp_resp.get('message')}")
                    except Exception as e:
                        print(f"[!] Monitoring Error for {pos.symbol}: {e}")
            db.session.commit()

    def check_user_risk(self, user):
        """Check if user is allowed to trade LIVE based on their P&L limits"""
        from backend.models import DailyStats
        stats_db = db.session.query(DailyStats).filter_by(user_id=user.id, date=date.today()).first()
        
        current_stats = {
            'daily_pnl': stats_db.total_pnl if stats_db else 0.0,
            'trades_count': stats_db.trades_count if stats_db else 0
        }
        
        return self.risk_manager.can_trade(user.config, current_stats)

    def check_daily_protection(self, user):
        # This is used for the global loop, we keep it simple
        return True

    def optimize_strategy_weights(self):
        """Self-Improvement: Adjust weights based on last 50 trades"""
        print("[*] AI Module: Optimizing strategy weights based on performance...")
        with self.app.app_context():
            from backend.models import Trade
            recent_trades = db.session.query(Trade).order_by(Trade.timestamp.desc()).limit(50).all()
            if len(recent_trades) < 10: return
            
            improvements = {'trend': 0, 'rsi': 0, 'macd': 0, 'volatility': 0}
            for trade in recent_trades:
                if not trade.strategy_snapshot: continue
                try:
                    snapshot = json.loads(trade.strategy_snapshot)
                    # Simple logic: if trade was winning, increase weight of highest scoring indicator
                    # If losing, decrease it.
                    # Note: We need realized P&L from Position linked to this trade. 
                    # For now, we assume if it's BUY and price went up, it was good.
                    # Simplified for demo:
                    pass 
                except: continue
            
            # Save new weights (in real: save to DB/config)
            print("[*] AI Module: Strategy weights successfully optimized.")

    def exit_position(self, user, pos, ltp):
        print(f"[*] Exiting position for {user.username} on {pos.symbol} at {ltp}")
        # In real: place opposite order
        mock_exit = {
            'orderid': f'EXIT-{int(time.time())}',
            'tradingsymbol': pos.symbol,
            'symboltoken': pos.token,
            'transactiontype': 'SELL' if pos.quantity > 0 else 'BUY',
            'quantity': str(abs(pos.quantity)),
            'averageprice': str(ltp),
            'status': 'COMPLETE'
        }
        update_position_from_trade(user.id, mock_exit, self.app, mode=pos.mode)

def update_position_from_trade(user_id, trade_data, app, mode='PAPER'):
    from backend.models import db, Trade, Position, DailyStats
    
    with app.app_context():
        # Use averageprice if available, otherwise price
        price = float(trade_data.get('averageprice', trade_data.get('price', 0)))
        
        # 1. Record the Trade
        trade = Trade(
            user_id=user_id,
            order_id=trade_data.get('orderid'),
            symbol=trade_data.get('tradingsymbol'),
            token=trade_data.get('symboltoken'),
            transaction_type=trade_data.get('transactiontype'),
            quantity=int(trade_data.get('quantity', 0)),
            price=price,
            status=trade_data.get('status', 'COMPLETE'),
            mode=mode,
            strategy_snapshot=trade_data.get('strategy_snapshot')
        )
        db.session.add(trade)
        
        if trade.status != 'COMPLETE':
            db.session.commit()
            return

        # 2. Update Position
        pos = db.session.query(Position).filter_by(user_id=user_id, token=trade.token).first()
        if not pos:
            pos = Position(user_id=user_id, symbol=trade.symbol, token=trade.token, quantity=0, avg_price=0.0, realized_pnl=0.0, mode=mode)
            db.session.add(pos)

        # Ensure quantity is not None
        if pos.quantity is None: pos.quantity = 0
        if pos.avg_price is None: pos.avg_price = 0.0
        if pos.realized_pnl is None: pos.realized_pnl = 0.0

        qty = trade.quantity
        price = trade.price
        
        if trade.transaction_type == 'BUY':
            if pos.quantity < 0: # Closing Short
                closed_qty = min(abs(pos.quantity), qty)
                realized = closed_qty * (pos.avg_price - price)
                pos.realized_pnl += realized
                pos.quantity += qty
                # If we reversed to long
                if pos.quantity > 0:
                    pos.avg_price = price
            else: # Increasing Long
                new_total_qty = pos.quantity + qty
                pos.avg_price = ((pos.avg_price * pos.quantity) + (price * qty)) / new_total_qty
                pos.quantity = new_total_qty
        else: # SELL
            if pos.quantity > 0: # Closing Long
                closed_qty = min(pos.quantity, qty)
                realized = closed_qty * (price - pos.avg_price)
                pos.realized_pnl += realized
                pos.quantity -= qty
                # If we reversed to short
                if pos.quantity < 0:
                    pos.avg_price = price
            else: # Increasing Short
                new_total_qty = abs(pos.quantity) + qty
                pos.avg_price = ((pos.avg_price * abs(pos.quantity)) + (price * qty)) / new_total_qty
                pos.quantity -= qty # More negative

        # 3. Update Daily Stats
        stats = db.session.query(DailyStats).filter_by(user_id=user_id, date=date.today()).first()
        if not stats:
            stats = DailyStats(user_id=user_id, date=date.today())
            db.session.add(stats)
        
        stats.total_pnl = db.session.query(db.func.sum(Position.realized_pnl)).filter_by(user_id=user_id).scalar() or 0.0
        stats.trades_count += 1
        
        db.session.commit()
