from flask_sqlalchemy import SQLAlchemy

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
    client_code = db.Column(db.String(50))
    password = db.Column(db.String(100))
    totp_secret = db.Column(db.String(100))
    redirect_url = db.Column(db.String(200))
    totp_app_url = db.Column(db.String(200))
    trading_mode = db.Column(db.String(10), default='PAPER')
    starting_capital = db.Column(db.Float, default=100000.0)

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
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

class Position(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symbol = db.Column(db.String(50))
    token = db.Column(db.String(20))
    avg_price = db.Column(db.Float, default=0.0)
    quantity = db.Column(db.Integer, default=0) # Positive for Long, Negative for Short
    realized_pnl = db.Column(db.Float, default=0.0)
    unrealized_pnl = db.Column(db.Float, default=0.0)
    last_price = db.Column(db.Float, default=0.0)
    mode = db.Column(db.String(10), default='PAPER') # LIVE/PAPER
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
    amount = db.Column(db.Float, default=399.0)
    status = db.Column(db.String(20), default='PENDING') # PENDING, APPROVED, REJECTED
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    username = db.Column(db.String(50)) # For easy display
