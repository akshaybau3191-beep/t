import time
import pyotp
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
            'MIDCPNIFTY': '99926017'
        }
        self.weights = {'trend': 30, 'momentum': 20, 'atr': 15, 'volume': 20, 'breakout': 15}
    
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
                    with self.app.app_context():
                        admin = db.session.query(User).filter_by(role='admin').first()
                        if admin:
                            # Auto-login admin if session missing
                            if admin.id not in user_sessions:
                                login_angel_one(admin, self.app)
                            
                            if admin.id in user_sessions:
                                self.scan_market(user_sessions[admin.id])
                        
                        self.monitor_positions()
                    time.sleep(10) # Scanner frequency
                else:
                    # Outside market hours: deep sleep to save CPU
                    time.sleep(60)
            except Exception as e:
                print(f"[!] Scanner Loop Error: {e}")
                time.sleep(10)

    def scan_market(self, smart_api):
        for name, token in self.indices.items():
            try:
                # 1. Fetch Real LTP
                exchange = "NSE" if name == "NIFTY" or name == "BANKNIFTY" else "NFO"
                # For indices, NSE is correct for NIFTY/BANKNIFTY spots
                ltp_resp = smart_api.ltpData(exchange, name, token)
                if not ltp_resp.get('status'): continue
                ltp = float(ltp_resp['data']['ltp'])

                # 2. Fetch Historical Data for Indicators (15min candles for today)
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
                    
                    closes = [float(c[4]) for c in candles]
                    ema21 = sum(closes[-21:]) / 21
                    ema50 = sum(closes[-50:]) / 50
                    momentum = ((ltp - closes[-10]) / closes[-10]) * 100
                    
                    data = {
                        'price': ltp,
                        'ema21': ema21,
                        'ema50': ema50,
                        'momentum': momentum,
                        'atrRatio': 1.5, # Placeholder or calculate ATR
                        'volumeRatio': 1.0, 
                        'isBreakout': ltp > max(closes[-20:-1])
                    }
                    
                    if self.score_index(data) >= 75:
                        self.dispatch_trade(name, data)
            except Exception as e:
                print(f"[!] Scanning Error for {name}: {e}")

    def score_index(self, data):
        score = 0
        if data['ema21'] > data['ema50'] and data['price'] > data['ema21']: score += self.weights['trend']
        elif data['ema21'] < data['ema50'] and data['price'] < data['ema21']: score += self.weights['trend']
        if data['momentum'] > 70 or data['momentum'] < 30: score += self.weights['momentum']
        if data['atrRatio'] > 1.2: score += self.weights['atr']
        if data['volumeRatio'] > 1.8: score += self.weights['volume']
        if data['isBreakout']: score += self.weights['breakout']
        return score

    def perform_daily_auto_login(self):
        with self.app.app_context():
            active_users = db.session.query(User).filter_by(is_active=True).all()
            for user in active_users:
                login_angel_one(user, self.app)

    def dispatch_trade(self, index, data):
        with self.app.app_context():
            from backend.models import User
            active_users = db.session.query(User).filter_by(is_active=True).all()
            for user in active_users:
                if user.is_active and user.last_login_date == date.today():
                    self.execute_for_user(user, index, data)

    def execute_for_user(self, user, index, data):
        if user.id not in user_sessions: return
        from backend.models import db, Position
        
        # Check if already in a position for this index (Simplified: using index name as token for now or mapping)
        # In real scenario, we'd check for specific option tokens
        token = self.indices.get(index)
        pos = db.session.query(Position).filter_by(user_id=user.id, token=token).first()
        if pos and pos.quantity != 0:
            return # Already in a position
            
        mode = user.config.trading_mode
        if mode == 'LIVE':
            print(f"[*] LIVE Trade Execution for {user.username} on {index}")
            # order_params = { ... }
            # resp = user_sessions[user.id].placeOrder(order_params)
            # if resp['status']: # record initial pending trade?
        else:
            print(f"[*] PAPER Trade Simulation for {user.username} on {index}")
            # Simulate a postback for paper trading
            mock_trade = {
                'orderid': f'MOCK-{int(time.time())}',
                'tradingsymbol': index,
                'symboltoken': token,
                'transactiontype': 'BUY', # Default to buy for demo
                'quantity': '50',
                'price': str(data['price']),
                'status': 'COMPLETE'
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
                            
                            # Exit Logic (Simplified: 5% target or 2% SL)
                            pnl_pct = (pos.unrealized_pnl / (abs(pos.quantity) * pos.avg_price)) * 100
                            if pnl_pct >= 5 or pnl_pct <= -2:
                                self.exit_position(user, pos, ltp)
                        else:
                            print(f"[!] LTP Fetch Failed for {pos.symbol}: {ltp_resp.get('message')}")
                    except Exception as e:
                        print(f"[!] Monitoring Error for {pos.symbol}: {e}")
            db.session.commit()

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
            mode=mode
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
