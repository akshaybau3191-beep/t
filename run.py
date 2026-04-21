import os
import sys
import threading
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- VENDORIZED DEPENDENCIES ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODULES_DIR = os.path.join(BASE_DIR, 'modules')
if os.path.exists(MODULES_DIR):
    sys.path.insert(0, MODULES_DIR)
    print(f"[*] Local modules path initialized: {MODULES_DIR}")

from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
import fcntl

# Import from our modularized backend
from backend.models import db, User, AngelConfig
from backend.engine import PythonTradingEngine, login_angel_one, user_sessions, update_position_from_trade
from backend.auth import login_required, admin_required

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'default-unsafe-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, "trading.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize DB with App
db.init_app(app)

def init_db():
    """Initialize database and create default admin if needed."""
    try:
        with app.app_context():
            print(f"[*] Checking/Creating database tables...")
            db.create_all()
            if not db.session.query(User).filter_by(username='admin').first():
                admin_pass = os.getenv('ADMIN_PASSWORD', 'admin123')
                admin = User(username='admin', password_hash=generate_password_hash(admin_pass), role='admin', is_active=True)
                db.session.add(admin)
                db.session.commit()
                print("[*] Default admin user verified/created.")
            else:
                print("[*] Admin user already exists.")
    except Exception as e:
        print(f"[!] Database Initialization Error: {e}")

def start_scanner_locked():
    """Start the scanner thread with a file lock to ensure only one instance runs across Gunicorn workers."""
    # Use /tmp for the lock file to avoid permission issues in the project directory
    lock_file_path = "/tmp/trading_bot_scanner.lock"
    try:
        app.scanner_lock_file = open(lock_file_path, 'w')
        fcntl.flock(app.scanner_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        
        engine = PythonTradingEngine(app)
        thread = threading.Thread(target=engine.run_scanner, daemon=True)
        thread.start()
        print("[*] Scanner thread started successfully with lock.")
    except (IOError, OSError):
        # This is normal for workers that are not the first one
        pass

# Run initialization on every import/worker start
init_db()
start_scanner_locked()

# --- ROUTES ---

# Moved catch-all routes to bottom

@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.json
        if not data.get('username') or not data.get('password'):
            return jsonify({'success': False, 'message': 'Username and password required'})
        if db.session.query(User).filter_by(username=data['username']).first():
            return jsonify({'success': False, 'message': 'Username exists'})
        new_user = User(username=data['username'], password_hash=generate_password_hash(data['password']))
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"[!] Registration Error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    user = db.session.query(User).filter_by(username=data['username']).first()
    if user and check_password_hash(user.password_hash, data['password']):
        session['user_id'] = user.id
        session['role'] = user.role
        session['username'] = user.username
        mode = user.config.trading_mode if user.config else 'PAPER'
        return jsonify({
            'success': True, 'role': user.role, 'username': user.username,
            'is_active': user.is_active, 'trading_mode': mode,
            'expiry': user.expiry_date.strftime('%Y-%m-%d') if user.expiry_date else None
        })
    return jsonify({'success': False, 'message': 'Invalid credentials'})

@app.route('/api/user/config', methods=['GET', 'POST'])
@login_required
def user_config():
    user = db.session.get(User, session['user_id'])
    if request.method == 'POST':
        data = request.json
        if not user.config:
            user.config = AngelConfig(user_id=user.id)
            db.session.add(user.config)
        user.config.api_key = data.get('api_key')
        user.config.client_code = data.get('client_code')
        user.config.password = data.get('password')
        user.config.totp_secret = data.get('totp_secret')
        user.config.redirect_url = data.get('redirect_url')
        user.config.totp_app_url = data.get('totp_app_url')
        db.session.commit()
        login_angel_one(user, app)
        return jsonify({'success': True})
    
    callback_url = f"{request.host_url.rstrip('/')}/api/angel/callback/{user.username}"
    postback_url = f"{request.host_url.rstrip('/')}/api/angel/postback/{user.username}"
    static_ip = "103.212.120.45"

    if not user.config:
        return jsonify({
            'callback_url': callback_url,
            'postback_url': postback_url,
            'static_ip': static_ip
        })
    
    return jsonify({
        'api_key': user.config.api_key, 'client_code': user.config.client_code, 
        'password': user.config.password, 'totp_secret': user.config.totp_secret,
        'redirect_url': user.config.redirect_url, 'totp_app_url': user.config.totp_app_url, 
        'trading_mode': user.config.trading_mode,
        'callback_url': callback_url,
        'postback_url': postback_url,
        'static_ip': static_ip
    })

@app.route('/api/user/positions', methods=['GET'])
@login_required
def user_positions():
    from backend.models import Position
    positions = db.session.query(Position).filter(Position.user_id == session['user_id'], Position.quantity != 0).all()
    return jsonify([{
        'symbol': p.symbol, 'token': p.token, 'qty': p.quantity,
        'avg_price': p.avg_price, 'realized': p.realized_pnl, 'unrealized': p.unrealized_pnl
    } for p in positions])

@app.route('/api/user/stats', methods=['GET'])
@login_required
def user_stats():
    from backend.models import DailyStats, Position, User, AngelConfig
    from datetime import date, datetime
    
    user_id = session['user_id']
    user = db.session.get(User, user_id)
    
    # 1. Daily Stats
    stats = db.session.query(DailyStats).filter_by(user_id=user_id, date=date.today()).first()
    daily_pnl = stats.total_pnl if stats else 0.0
    daily_trades = stats.trades_count if stats else 0
    
    # 2. Total Real Profit
    real_positions = db.session.query(Position).filter_by(user_id=user_id, mode='LIVE').all()
    total_real_profit = sum(p.realized_pnl for p in real_positions)
    
    # 3. CAGR Calculation
    # CAGR = [(End Value / Start Value) ^ (1 / years)] - 1
    starting_capital = user.config.starting_capital if user.config else 100000.0
    current_value = starting_capital + total_real_profit
    
    # Calculate years active (min 1 day to avoid div by zero)
    if user.last_login_date:
        # Assuming registration or first login as start date. 
        # For demo, let's say they started 30 days ago if no data.
        days_active = max(1, (date.today() - (user.last_login_date - timedelta(days=30))).days)
    else:
        days_active = 30
        
    years = days_active / 365.0
    cagr = ((current_value / starting_capital) ** (1 / years) - 1) * 100 if starting_capital > 0 else 0
    
    # 4. Market Status
    engine = PythonTradingEngine(app)
    is_open = engine.is_market_open()
    
    return jsonify({
        'daily_pnl': daily_pnl,
        'trades': daily_trades,
        'total_real_profit': total_real_profit,
        'cagr': cagr,
        'is_market_open': is_open
    })

@app.route('/api/angel/postback/<username>', methods=['POST'])
def angel_postback(username):
    try:
        data = request.json
        print(f"[*] Order Postback for {username}: {data}")
        
        user = db.session.query(User).filter_by(username=username).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
            
        # Background task or direct call
        update_position_from_trade(user.id, data, app)
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"[!] Postback Error for {username}: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_users():
    users = db.session.query(User).all()
    return jsonify([{
        'id': u.id, 'username': u.username, 'role': u.role, 'is_active': u.is_active,
        'expiry': u.expiry_date.strftime('%Y-%m-%d') if u.expiry_date else 'N/A',
        'last_login': u.last_login_date.strftime('%Y-%m-%d') if u.last_login_date else 'Never'
    } for u in users])

@app.route('/api/admin/toggle_user', methods=['POST'])
@admin_required
def toggle_user():
    data = request.json
    user = db.session.get(User, data['user_id'])
    if user:
        if not user.is_active:
            user.is_active = True
            user.expiry_date = datetime.now(timezone.utc) + timedelta(days=30)
            now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
            if now.hour >= 8:
                login_angel_one(user, app)
        else:
            user.is_active = False
            user_sessions.pop(user.id, None)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/api/shutdown', methods=['POST'])
@admin_required
def shutdown():
    os._exit(0)

# Catch-all routes at the bottom
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    # When running directly (development), use the Flask dev server
    # init_db() and start_scanner_locked() already ran above at module level
    app.run(host='0.0.0.0', port=8000, debug=False)
