from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(10), default='user')
    is_active = db.Column(db.Boolean, default=False)
    expiry_date = db.Column(db.DateTime, nullable=True)
    last_login_date = db.Column(db.Date, nullable=True)
    config = db.relationship('AngelConfig', backref='user', uselist=False)

class AngelConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    api_key = db.Column(db.String(100))
    api_secret = db.Column(db.String(100))
    client_code = db.Column(db.String(50))
    password = db.Column(db.String(100))
    totp_secret = db.Column(db.String(100))
    redirect_url = db.Column(db.String(200))
    totp_app_url = db.Column(db.String(200))
    trading_mode = db.Column(db.String(10), default='PAPER')
    starting_capital = db.Column(db.Float, default=100000.0)
    max_daily_loss_pct = db.Column(db.Float, default=3.0)
    risk_per_trade_pct = db.Column(db.Float, default=2.0)
    min_confidence_score = db.Column(db.Integer, default=75)
    trailing_sl_pct = db.Column(db.Float, default=1.0) # Move SL by 1% for every 1% profit

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_id = db.Column(db.String(100), unique=True)
    symbol = db.Column(db.String(50))
    token = db.Column(db.String(20))
    transaction_type = db.Column(db.String(10)) # BUY/SELL
    quantity = db.Column(db.Integer)
    price = db.Column(db.Float)
    status = db.Column(db.String(20)) # COMPLETE, REJECTED, etc.
    mode = db.Column(db.String(10), default='PAPER') # LIVE/PAPER
    reason = db.Column(db.String(100))
    strategy_snapshot = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

class Position(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symbol = db.Column(db.String(50))
    token = db.Column(db.String(20))
    avg_price = db.Column(db.Float, default=0.0)
    quantity = db.Column(db.Integer, default=0)
    realized_pnl = db.Column(db.Float, default=0.0)
    unrealized_pnl = db.Column(db.Float, default=0.0)
    last_price = db.Column(db.Float, default=0.0)
    mode = db.Column(db.String(10), default='PAPER')
    sl_price = db.Column(db.Float, nullable=True)
    tp_price = db.Column(db.Float, nullable=True)
    tsl_price = db.Column(db.Float, nullable=True) # Trailing SL Price
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

class DailyStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, default=db.func.current_date())
    total_pnl = db.Column(db.Float, default=0.0)
    trades_count = db.Column(db.Integer, default=0)
    win_rate = db.Column(db.Float, default=0.0)

class SubscriptionRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    upi_ref = db.Column(db.String(100), nullable=False)
    proof_image = db.Column(db.String(200)) # Path to uploaded screenshot
    amount = db.Column(db.Float, default=399.0)
    status = db.Column(db.String(20), default='PENDING') # PENDING, APPROVED, REJECTED
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    username = db.Column(db.String(50))

class SystemStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    engine_status = db.Column(db.String(20), default='Offline')
    engine_task = db.Column(db.String(100), default='Waiting')
    scanned_count = db.Column(db.Integer, default=0)
    force_scan_trigger = db.Column(db.Boolean, default=False)
    last_update = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

class Signal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    index = db.Column(db.String(20))
    symbol = db.Column(db.String(50))
    token = db.Column(db.String(20))
    signal_type = db.Column(db.String(10)) # CE/PE
    price = db.Column(db.Float)
    confidence = db.Column(db.Integer)
    sl = db.Column(db.Float)
    tp = db.Column(db.Float)
    strategy_snapshot = db.Column(db.Text)
    is_processed = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

def update_system_status(task, count, status='Online'):
    """Atomic Status Update to avoid Database Locks in Production"""
    from sqlalchemy import text
    try:
        # 1. Use a fresh, independent connection for the heartbeat
        with db.engine.connect() as conn:
            # Check if record exists
            result = conn.execute(text("SELECT id FROM system_status LIMIT 1")).fetchone()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if result:
                # Update existing
                conn.execute(text(f"UPDATE system_status SET engine_status='{status}', engine_task='{task}', scanned_count={count}, last_update='{now}' WHERE id={result[0]}"))
            else:
                # Insert new
                conn.execute(text(f"INSERT INTO system_status (engine_status, engine_task, scanned_count, last_update) VALUES ('{status}', '{task}', {count}, '{now}')"))
            
            conn.commit()
    except Exception as e:
        print(f"[!] Atomic Heartbeat Failed: {e}")
