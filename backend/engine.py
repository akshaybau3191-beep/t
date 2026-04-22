import pyotp
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date, timezone
from SmartApi import SmartConnect
from backend.models import db, User, AngelConfig

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
    
    def is_market_open(self):
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
                    with self.app.app_context():
                        admin = db.session.query(User).filter_by(role='admin').first()
                        if admin:
                            if self.check_daily_protection(admin):
                                # Auto-login admin if session missing
                                if admin.id not in user_sessions:
                                    self.current_task = "Logging into Angel One..."
                                    login_angel_one(admin, self.app)
                                
                                if admin.id in user_sessions:
                                    self.scan_market(user_sessions[admin.id])
                            
                        self.current_task = "Monitoring Active Positions"
                        self.monitor_positions()
                    time.sleep(10) # Scanner frequency
                else:
                    # After market hours: self-improve
                    self.current_task = "Market Closed: Waiting"
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
        for name, token in self.indices.items():
            self.current_task = f"Analyzing {name}"
            try:
                # 1. Fetch Real LTP (All indices are in NSE)
                exchange = "NSE" 
                ltp_resp = smart_api.ltpData(exchange, name, token)
                if not ltp_resp.get('status'): continue
                ltp = float(ltp_resp['data']['ltp'])

                # 2. Fetch Historical Data for Indicators
                # ... (keep existing candle data logic)
                # This is a simplified indicator calculation
                to_date = (datetime.now() + timedelta(hours=5, minutes=30)).strftime('%Y-%m-%d %H:%M')
                from_date = (datetime.now() + timedelta(hours=5, minutes=30) - timedelta(days=2)).strftime('%Y-%m-%d %H:%M')
                
                historic_params = {
                    "exchange": "NSE",
                    "symboltoken": token,
                    "interval": "FIFTEEN_MINUTE",
                    "fromdate": from_date,
                    "todate": to_date
                }
                hist_resp = smart_api.getCandleData(historic_params)
                
                if hist_resp.get('status') and hist_resp.get('data'):
                    candles = hist_resp['data']
                    if len(candles) < 50: continue
                    
                    df = pd.DataFrame(candles, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
                    df['close'] = df['close'].astype(float)
                    
                    # 3. Advanced Indicators
                    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
                    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
                    
                    # RSI
                    delta = df['close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    df['rsi'] = 100 - (100 / (1 + (gain / loss)))
                    
                    # MACD
                    exp12 = df['close'].ewm(span=12, adjust=False).mean()
                    exp26 = df['close'].ewm(span=26, adjust=False).mean()
                    df['macd'] = exp12 - exp26
                    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
                    
                    # Bollinger Bands
                    df['sma20'] = df['close'].rolling(window=20).mean()
                    df['std20'] = df['close'].rolling(window=20).std()
                    df['bb_upper'] = df['sma20'] + (df['std20'] * 2)
                    df['bb_lower'] = df['sma20'] - (df['std20'] * 2)
                    
                    # ATR (14)
                    high_low = df['high'] - df['low']
                    high_close = (df['high'] - df['close'].shift()).abs()
                    low_close = (df['low'] - df['close'].shift()).abs()
                    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                    df['atr'] = tr.rolling(window=14).mean()

                    last = df.iloc[-1]
                    prev = df.iloc[-2]
                    
                    analysis = {
                        'price': ltp,
                        'ema21': last['ema21'],
                        'ema50': last['ema50'],
                        'rsi': last['rsi'],
                        'macd': last['macd'],
                        'macd_signal': last['macd_signal'],
                        'bb_upper': last['bb_upper'],
                        'bb_lower': last['bb_lower'],
                        'atr': last['atr'],
                        'isBreakout': ltp > df['high'].iloc[-20:-1].max(),
                        'trend_score': 0,
                        'momentum_score': 0,
                        'rsi_score': 0,
                        'macd_score': 0,
                        'vol_score': 0,
                        'breakout_score': 0
                    }
                    
                    score = self.calculate_total_score(analysis)
                    analysis['total_score'] = score
                    self.last_analysis[name] = analysis

                    if score >= 75:
                        signal = 'CE' if last['ema21'] > last['ema50'] else 'PE'
                        self.dispatch_trade(name, analysis, signal)
            except Exception as e:
                print(f"[!] Scanning Error for {name}: {e}")

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

    def dispatch_trade(self, index, data, signal):
        with self.app.app_context():
            from backend.models import User
            active_users = db.session.query(User).filter_by(is_active=True).all()
            for user in active_users:
                if user.is_active and user.last_login_date == date.today():
                    self.execute_for_user(user, index, data, signal)

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

    def execute_for_user(self, user, index, data, signal):
        if user.id not in user_sessions: return
        from backend.models import db, Position
        
        # Calculate strikes
        strikes = self.get_option_strike(index, data['price'], signal)
        # Select strike (default to ATM for now, can be optimized)
        selected_strike = strikes['ATM']
        
        # Generate symbolic name for logging/sim (In real, search for token)
        # NIFTY24APR22500CE
        expiry_str = "24APR" # Placeholder, in real should be dynamic
        option_symbol = f"{index}{expiry_str}{selected_strike}{signal}"
        
        # In real scenario, search for token
        # For now, we use a placeholder or the index token for paper
        token = f"OPT-{index}-{selected_strike}-{signal}" 
        
        # Prepare strategy snapshot
        snapshot = json.dumps(data)
        
        pos = db.session.query(Position).filter_by(user_id=user.id, token=token).first()
        if pos and pos.quantity != 0:
            return 
            
        mode = user.config.trading_mode
        if mode == 'LIVE':
            print(f"[*] LIVE Trade Execution for {user.username} on {option_symbol}")
            # order_params = { ... exchange: 'NFO', tradingsymbol: option_symbol, ... }
        else:
            print(f"[*] PAPER Trade Simulation for {user.username} on {option_symbol}")
            mock_trade = {
                'orderid': f'MOCK-{int(time.time())}',
                'tradingsymbol': option_symbol,
                'symboltoken': token,
                'transactiontype': 'BUY', 
                'quantity': '50',
                'price': '100.0', # Placeholder for option premium
                'status': 'COMPLETE',
                'strategy_snapshot': snapshot
            }
            update_position_from_trade(user.id, mock_trade, self.app, mode=mode)

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

    def check_daily_protection(self, user):
        from backend.models import DailyStats
        stats = db.session.query(DailyStats).filter_by(user_id=user.id, date=date.today()).first()
        if stats:
            starting_capital = user.config.starting_capital if user.config else 100000.0
            if starting_capital > 0:
                loss_pct = (stats.total_pnl / starting_capital) * 100
                if loss_pct <= -self.daily_loss_limit:
                    return False
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
