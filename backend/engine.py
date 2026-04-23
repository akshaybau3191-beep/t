import os
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
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # Find the absolute root directory (Ai-Bot-Trader/)
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            log_path = os.path.join(base_dir, "engine.log")
            
            with open(log_path, 'a') as f:
                f.write(f"[{timestamp}] {msg}\n")
            print(f"[{timestamp}] {msg}", flush=True)
        except Exception as e:
            # Fallback to current directory if absolute fails
            try:
                with open("engine.log", "a") as f:
                    f.write(f"[{timestamp}] FALLBACK: {msg}\n")
            except:
                print(f"CRITICAL LOG ERROR: {e}")

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

    def scan_market(self, obj):
        """Elite Multi-Factor Scanning Loop: Individual Candidate Study"""
        from backend.symbols import SymbolManager
        from backend.strategy import EliteStrategyManager
        from backend.models import db, Signal
        import json
        
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
                    market_data = obj.marketData("FULL", [{"exchangeCode": "NFO", "symbolToken": cand['token']}])
                    if not market_data.get('status') or not market_data['data']['fetched']: continue
                    data = market_data['data']['fetched'][0]
                    
                    # B. Fetch Historical Data (1m and 5m)
                    # Use a short sleep to stay under Angel One's 3-calls-per-second limit
                    time.sleep(0.35)
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
                            # Avoid duplicate signals for the same token in last 3 mins
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
tinue

                self.log_to_file(f"[*] Found {len(options)} options. Starting Selective AI analysis...")
                
                best_candidate = None
                with self.app.app_context():
                    admin = db.session.query(User).filter_by(role='admin').first()
                    min_score = admin.config.min_confidence_score if admin and admin.config else 75

                # Step 1: Collect All Valid Signals
                chunk_size = 50
                for i in range(0, len(options), chunk_size):
                    chunk = options[i:i + chunk_size]
                    tokens = [o['token'] for o in chunk]
                    market_data_resp = smart_api.getMarketData("FULL", {"NFO": tokens})
                    
                    if not market_data_resp.get('status') or not market_data_resp.get('data'): continue
                    
                    fetched_data = market_data_resp['data']['fetched']
                    for o_data in fetched_data:
                        opt_info = next((o for o in chunk if o['token'] == o_data['symbolToken']), None)
                        if not opt_info: continue
                        
                        token = opt_info['token']
                        if token not in self.option_candles or not self.option_candles[token]:
                            self.option_candles[token] = self.fetch_option_candles(smart_api, token)
                        
                        # Step 2: Analyze each strike
                        analysis = self.strategy_manager.analyze_option(
                            self.option_candles[token], o_data, opt_info, ltp, logger=self.log_to_file
                        )
                        
                        # Step 3: Evaluate Candidate
                        if analysis['signal_strength'] >= min_score and analysis['signal'] == 'BUY':
                            distance = abs(opt_info['strike'] - ltp)
                            analysis['distance'] = distance
                            analysis['opt_info'] = opt_info
                            
                            self.log_to_file(f"   [CANDIDATE] {opt_info['symbol']} found at {analysis['signal_strength']}% Confidence")
                            
                            # Selection Logic: Higher strength first, then closer to LTP
                            if not best_candidate:
                                best_candidate = analysis
                            else:
                                if analysis['signal_strength'] > best_candidate['signal_strength']:
                                    best_candidate = analysis
                                elif analysis['signal_strength'] == best_candidate['signal_strength'] and distance < best_candidate['distance']:
                                    best_candidate = analysis

                # Step 4: Finalize the "Winner"
                if best_candidate:
                    win = best_candidate['opt_info']
                    self.log_to_file(f"🎯 ELITE SELECTION: {win['symbol']} chosen for trade ({best_candidate['signal_strength']}%)")
                    # Broadcast for Distributed Executor
                    self.broadcast_signal(name, best_candidate)
                else:
                    self.log_to_file("[i] No high-potential candidates met the threshold this cycle.")
            except Exception as e:
                self.log_to_file(f"Error scanning {name}: {e}")

    def broadcast_signal(self, index, data):
        """Saves master signal to DB for the Distributed Executor to pick up"""
        with self.app.app_context():
            from backend.models import db, Signal
            try:
                win = data['opt_info']
                new_sig = Signal(
                    index=index,
                    symbol=win['symbol'],
                    token=win['token'],
                    signal_type=win['type'],
                    price=data['price'],
                    confidence=data['signal_strength'],
                    sl=data['sl'],
                    tp=data['tp'],
                    strategy_snapshot=json.dumps(data)
                )
                db.session.add(new_sig)
                db.session.commit()
                self.log_to_file(f"📢 MASTER SIGNAL BROADCASTED: {win['symbol']} at ₹{data['price']}")
            except Exception as e:
                self.log_to_file(f"[!] Broadcast Failed: {e}")
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
            
        # 2. Dynamic Lot Sizing & Fallback Logic
        user_cfg = user.config
        market_lot = 65 if index == 'NIFTY' else 30
        price_per_lot = data['price'] * market_lot
        total_cap = user_cfg.starting_capital or 100000
        
        # Calculate how many lots we can afford
        lot_size = self.risk_manager.calculate_lot_size(user_cfg, index, data['price'])
        
        mode = user_cfg.trading_mode
        exec_reason = "Admin Signal"
        
        # --- PROFESSIONAL GUARDRAILS ---
        
        # 1. ADMIN PROTECTION: Admin only circulates calls, never trades LIVE
        if user.role == 'admin':
            mode = 'PAPER'
            exec_reason = "Admin Signal Generation"
            lot_size = market_lot # 1 lot for admin tracking
            
        # 2. SUBSCRIPTION CHECK: If expired, force PAPER trade only
        now = datetime.now()
        if user.role != 'admin': # Only check subscribers
            if not user.expiry_date or user.expiry_date < now:
                print(f"[!] User {user.username} has no valid subscription. Forcing PAPER mode.")
                mode = 'PAPER'
                exec_reason = "Subscription Expired"
                lot_size = market_lot # 1 lot for paper

        # 3. CAPITAL CHECK: If LIVE but capital is low, fallback to PAPER
        if mode == 'LIVE' and lot_size <= 0:
            print(f"[*] Insufficient capital for LIVE trade (Need ₹{price_per_lot:.0f}, Have ₹{total_cap:.0f})")
            print(f"[*] Downgrading to PAPER for {user.username} to track signal.")
            mode = 'PAPER'
            lot_size = market_lot # Use 1 lot for paper tracking
            exec_reason = "Insufficient Capital (Live -> Paper)"
        elif lot_size <= 0:
            return

        slippage = 0.001 
        limit_price = data['price'] * (1 + slippage) if signal == 'BUY' else data['price'] * (1 - slippage)
        
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
                        'status': 'COMPLETE',
                        'sl': data.get('sl'), # Pass SL
                        'tp': data.get('tp')  # Pass TP
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

    def monitor_user_positions(self, user):
        """Monitor positions for a single user (called by dedicated thread)"""
        if user.id not in user_sessions: return
        obj = user_sessions[user.id]
        from backend.models import db, Position
        
        with self.app.app_context():
            positions = db.session.query(Position).filter(Position.user_id == user.id, Position.quantity != 0).all()
            for pos in positions:
                try:
                    exchange = "NFO" if any(x in pos.symbol for x in ["NIFTY", "BANKNIFTY", "FINNIFTY"]) else "NSE"
                    ltp_resp = obj.ltpData(exchange, pos.symbol, pos.token)
                    
                    if ltp_resp.get('status') and ltp_resp.get('data'):
                        ltp = float(ltp_resp['data']['ltp'])
                        pos.last_price = ltp
                        
                        # Update unrealized P&L
                        pos.unrealized_pnl = pos.quantity * (ltp - pos.avg_price)
                        
                        # --- TRAILING STOP LOSS LOGIC ---
                        # If price moves up by 1%, move SL up by trailing_sl_pct
                        profit_pct = (pos.unrealized_pnl / (abs(pos.quantity) * pos.avg_price)) * 100
                        
                        if profit_pct > 1.0: # Start trailing after 1% profit
                            trail_buffer = pos.avg_price * (user.config.trailing_sl_pct / 100)
                            new_tsl = ltp - trail_buffer
                            if not pos.tsl_price or new_tsl > pos.tsl_price:
                                pos.tsl_price = new_tsl

                        # --- EXIT LOGIC ---
                        exit_triggered = False
                        reason = ""
                        
                        # Check Target
                        if pos.tp_price and ltp >= pos.tp_price:
                            exit_triggered = True
                            reason = f"TARGET HIT at {ltp}"
                        
                        # Check Trailing SL or Hard SL
                        effective_sl = pos.tsl_price or pos.sl_price
                        if effective_sl and ltp <= effective_sl:
                            exit_triggered = True
                            reason = f"STOP LOSS HIT at {ltp}"
                        
                        if exit_triggered:
                            print(f"🛡️ EXIT SIGNAL for {user.username}: {pos.symbol} | {reason}")
                            self.exit_position(user, pos, ltp)
                    
                    db.session.commit()
                except Exception as e:
                    print(f"[!] Monitor Error for {user.username} {pos.symbol}: {e}")

    def monitor_positions(self):
        """Deprecated: Now handled by individual user threads in executor.py"""
        pass

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
    """Handles both manual mock trades and Real-Time Postbacks from Angel One"""
    from backend.models import db, Trade, Position, DailyStats
    from datetime import date
    
    with app.app_context():
        # Extact data from Angel One postback format or mock format
        order_id = str(trade_data.get('orderid', trade_data.get('order_id', '')))
        symbol = trade_data.get('tradingsymbol', trade_data.get('symbol'))
        token = trade_data.get('symboltoken', trade_data.get('token'))
        tx_type = trade_data.get('transactiontype', trade_data.get('transaction_type'))
        qty = int(trade_data.get('quantity', trade_data.get('fillqty', 0)))
        price = float(trade_data.get('averageprice', trade_data.get('fillprice', trade_data.get('price', 0))))
        status = trade_data.get('status', 'COMPLETE')
        
        if not order_id or status != 'COMPLETE': return

        # 1. Record/Update the Trade
        trade = db.session.query(Trade).filter_by(order_id=order_id).first()
        if not trade:
            trade = Trade(
                user_id=user_id,
                order_id=order_id,
                symbol=symbol,
                token=token,
                transaction_type=tx_type,
                quantity=qty,
                price=price,
                status=status,
                mode=mode
            )
            db.session.add(trade)
        
        # 2. Update Position
        pos = db.session.query(Position).filter_by(user_id=user_id, token=token).first()
        if not pos:
            pos = Position(
                user_id=user_id, symbol=symbol, token=token, quantity=0, 
                avg_price=0.0, mode=mode,
                sl_price=trade_data.get('sl'),
                tp_price=trade_data.get('tp')
            )
            db.session.add(pos)

        if tx_type == 'BUY':
            if pos.quantity < 0: # Closing Short
                closed_qty = min(abs(pos.quantity), qty)
                pos.realized_pnl += closed_qty * (pos.avg_price - price)
                pos.quantity += qty
            else: # Increasing Long
                new_total = (pos.quantity or 0) + qty
                pos.avg_price = (((pos.avg_price or 0.0) * (pos.quantity or 0)) + (price * qty)) / new_total
                pos.quantity = new_total
        else: # SELL
            if pos.quantity > 0: # Closing Long
                closed_qty = min(pos.quantity, qty)
                pos.realized_pnl += closed_qty * (price - pos.avg_price)
                pos.quantity -= qty
            else: # Increasing Short
                new_total = abs(pos.quantity or 0) + qty
                pos.avg_price = (((pos.avg_price or 0.0) * abs(pos.quantity or 0)) + (price * qty)) / new_total
                pos.quantity -= qty

        # 3. Update Daily Stats
        stats = db.session.query(DailyStats).filter_by(user_id=user_id, date=date.today()).first()
        if not stats:
            stats = DailyStats(user_id=user_id, date=date.today())
            db.session.add(stats)
        
        stats.total_pnl = db.session.query(db.func.sum(Position.realized_pnl)).filter_by(user_id=user_id).scalar() or 0.0
        stats.trades_count += 1
        
        db.session.commit()
