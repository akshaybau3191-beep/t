import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

# --- VENDORIZED DEPENDENCIES ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODULES_DIR = os.path.join(BASE_DIR, 'modules')
if os.path.exists(MODULES_DIR):
    sys.path.insert(0, MODULES_DIR)
    print(f"[*] Local modules path initialized: {MODULES_DIR}")

from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()

from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import fcntl

# Import from our modularized backend
from backend.models import db, User, AngelConfig
from backend.engine import PythonTradingEngine, login_angel_one, user_sessions, update_position_from_trade
from backend.auth import login_required, admin_required

app = Flask(__name__)
CORS(app, supports_credentials=True) # Enable CORS for frontend
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'default-unsafe-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, "trading.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Added: Upload folder for payment proofs
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
# Added: Database Timeout for Concurrent Scanner Threads
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"connect_args": {"timeout": 30}}
# Added: Persistent Session Management
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=31)
app.config['SESSION_COOKIE_NAME'] = 'elite_trader_session'

# Initialize DB with App
db.init_app(app)

def init_db():
    """Initialize database and create default admin if needed."""
    try:
        with app.app_context():
            print(f"[*] Checking/Creating database tables...")
            db.create_all()
            
            # Simple Migration: Add starting_capital to angel_config if missing
            try:
                import sqlite3
                from sqlalchemy import text
                db_path = os.path.join(BASE_DIR, "trading.db")
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(angel_config)")
                columns = [c[1] for c in cursor.fetchall()]
                
                # Simple Migration: Add missing columns to angel_config
                columns_to_add = [
                    ('starting_capital', 'FLOAT DEFAULT 100000.0'),
                    ('max_daily_loss_pct', 'FLOAT DEFAULT 3.0'),
                    ('risk_per_trade_pct', 'FLOAT DEFAULT 2.0'),
                    ('min_confidence_score', 'INTEGER DEFAULT 75'),
                    ('api_secret', 'VARCHAR(100)')
                ]
                for col, col_type in columns_to_add:
                    if col not in columns:
                        try:
                            db.session.execute(text(f"ALTER TABLE angel_config ADD COLUMN {col} {col_type}"))
                            db.session.commit()
                            print(f"[*] Migrated: Added {col} to angel_config")
                        except Exception:
                            db.session.rollback()
                
                cursor.execute("PRAGMA table_info(trade)")
                trade_columns = [c[1] for c in cursor.fetchall()]
                if 'strategy_snapshot' not in trade_columns:
                    try:
                        db.session.execute(text("ALTER TABLE trade ADD COLUMN strategy_snapshot TEXT"))
                        db.session.commit()
                    except Exception: db.session.rollback()
                
                if 'reason' not in trade_columns:
                    try:
                        db.session.execute(text("ALTER TABLE trade ADD COLUMN reason VARCHAR(100)"))
                        db.session.commit()
                    except Exception: db.session.rollback()
                
                # Ensure every user has an AngelConfig
                cursor.execute("SELECT id FROM user")
                users = cursor.fetchall()
                for (uid,) in users:
                    cursor.execute("SELECT id FROM angel_config WHERE user_id=?", (uid,))
                    if not cursor.fetchone():
                        cursor.execute("INSERT INTO angel_config (user_id, starting_capital, max_daily_loss_pct, risk_per_trade_pct, min_confidence_score, trading_mode) VALUES (?, 100000.0, 3.0, 2.0, 75, 'PAPER')", (uid,))
                
                conn.commit()
                conn.close()
                print("[*] Database schema and records verified.")
            except Exception as e:
                print(f"[!] Migration Error: {e}")

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
        app.trading_engine = engine # Store on app
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
        user.last_login_date = datetime.now(timezone.utc).date()
        db.session.commit()
        session['user_id'] = user.id
        session['role'] = user.role
        session['username'] = user.username
        session.permanent = True # Ensure session persists for 31 days
        mode = user.config.trading_mode if user.config else 'PAPER'
        return jsonify({
            'success': True, 'role': user.role, 'username': user.username,
            'is_active': user.is_active, 'trading_mode': mode,
            'expiry': user.expiry_date.strftime('%Y-%m-%d') if user.expiry_date else None
        })
    return jsonify({'success': False, 'message': 'Invalid credentials'})

@app.route('/api/auth/me', methods=['GET'])
def get_me():
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if user:
            mode = user.config.trading_mode if user.config else 'PAPER'
            return jsonify({
                'success': True, 'username': user.username, 'role': user.role,
                'is_active': user.is_active, 'trading_mode': mode,
                'expiry': user.expiry_date.strftime('%Y-%m-%d') if user.expiry_date else None
            })
    return jsonify({'success': False})

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/user/broker-config', methods=['GET', 'POST'])
@login_required
def user_broker_config():
    user = db.session.get(User, session['user_id'])
    if request.method == 'POST':
        data = request.json
        if not user.config:
            user.config = AngelConfig(user_id=user.id)
            db.session.add(user.config)
        user.config.api_key = data.get('api_key')
        user.config.api_secret = data.get('api_secret')
        user.config.client_code = data.get('client_code')
        user.config.password = data.get('password')
        user.config.totp_secret = data.get('totp_secret')
        db.session.commit()
        # Automatically login after save
        login_angel_one(user, app)
        return jsonify({'success': True})
    
    callback_url = f"{request.host_url.rstrip('/')}/api/angel/callback/{user.username}"
    postback_url = f"{request.host_url.rstrip('/')}/api/angel/postback/{user.username}"
    static_ip = "3.6.231.207"

    if not user.config:
        return jsonify({
            'callback_url': callback_url, 'postback_url': postback_url, 'static_ip': static_ip
        })
    
    return jsonify({
        'api_key': user.config.api_key, 'api_secret': user.config.api_secret,
        'client_code': user.config.client_code, 
        'password': user.config.password, 'totp_secret': user.config.totp_secret,
        'trading_mode': user.config.trading_mode,
        'callback_url': callback_url, 'postback_url': postback_url, 'static_ip': static_ip
    })

@app.route('/api/user/history', methods=['GET'])
@login_required
def get_trade_history():
    from backend.models import Trade
    user = db.session.get(User, session['user_id'])
    trades = db.session.query(Trade).filter_by(user_id=user.id).order_by(Trade.timestamp.desc()).limit(50).all()
    
    history = []
    for t in trades:
        history.append({
            'symbol': t.symbol,
            'type': t.transaction_type,
            'qty': t.quantity,
            'price': t.price,
            'status': t.status,
            'mode': t.mode,
            'time': t.timestamp.strftime('%H:%M:%S'),
            'reason': t.reason
        })
    return jsonify(history)

@app.route('/api/user/positions', methods=['GET'])
@login_required
def user_positions():
    from backend.models import Position
    positions = db.session.query(Position).filter(Position.user_id == session['user_id'], Position.quantity != 0).all()
    return jsonify([{
        'symbol': p.symbol, 'token': p.token, 'qty': p.quantity,
        'avg_price': p.avg_price, 'realized': p.realized_pnl, 'unrealized': p.unrealized_pnl
    } for p in positions])

@app.route('/api/market/indices', methods=['GET'])
@login_required
def market_indices():
    # Retrieve admin session to fetch LTP data
    admin_user = db.session.query(User).filter_by(role='admin').first()
    if admin_user and admin_user.id not in user_sessions:
        login_angel_one(admin_user, app)
        
    if not admin_user or admin_user.id not in user_sessions:
        return jsonify({'success': False, 'message': 'Engine not logged in'}), 503
    smart_api = user_sessions[admin_user.id]
    engine = PythonTradingEngine(app)
    result = []
    for name, token in engine.indices.items():
        try:
            # Use NSE for index LTP
            ltp_resp = smart_api.ltpData('NSE', name, token)
            if not ltp_resp.get('status'):
                continue
            ltp = float(ltp_resp['data']['ltp'])
            # Simple change calculation: compare with EMA21 if available, else 0%
            # For demo, we set change to 0.0
            change = 0.0
            result.append({'name': name, 'ltp': ltp, 'change': change})
        except Exception as e:
            print(f"[!] Market index fetch error for {name}: {e}")
            continue
    return jsonify(result)

@app.route('/api/market/candles/<index>', methods=['GET'])
@login_required
def market_candles(index):
    admin_user = db.session.query(User).filter_by(role='admin').first()
    if not admin_user or admin_user.id not in user_sessions:
        return jsonify({'success': False, 'message': 'Engine not logged in'}), 503
    
    smart_api = user_sessions[admin_user.id]
    engine = PythonTradingEngine(app)
    data = engine.get_candle_data(smart_api, index)
    analysis = engine.get_market_analysis(index)
    
    return jsonify({
        'candles': data,
        'analysis': analysis
    })

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
    
    # 4. Market Status & Current Task
    engine = PythonTradingEngine(app)
    is_open = engine.is_market_open()
    
    engine_task = "Starting..."
    scanned_count = 0
    if hasattr(app, 'trading_engine'):
        engine_task = app.trading_engine.current_task
        scanned_count = app.trading_engine.scanned_count
    
    return jsonify({
        'daily_pnl': daily_pnl,
        'trades': daily_trades,
        'total_real_profit': total_real_profit,
        'cagr': cagr,
        'is_market_open': is_open,
        'engine_task': engine_task,
        'scanned_count': scanned_count
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

@app.route('/api/subscription/request', methods=['POST'])
@login_required
def submit_sub_request():
    from backend.models import SubscriptionRequest
    from werkzeug.utils import secure_filename
    
    upi_ref = request.form.get('upi_ref')
    proof_file = request.files.get('proof')
    user = db.session.get(User, session['user_id'])
    
    filename = None
    if proof_file:
        filename = secure_filename(f"{user.username}_{int(time.time())}_{proof_file.filename}")
        proof_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    
    new_req = SubscriptionRequest(
        user_id=user.id,
        username=user.username,
        upi_ref=upi_ref,
        proof_image=filename,
        amount=399.0,
        status='PENDING'
    )
    db.session.add(new_req)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Request submitted with proof! Admin will verify.'})

@app.route('/api/subscription/my_request', methods=['GET'])
@login_required
def get_my_sub_request():
    from backend.models import SubscriptionRequest
    user = db.session.get(User, session['user_id'])
    req = db.session.query(SubscriptionRequest).filter_by(user_id=user.id).order_by(SubscriptionRequest.timestamp.desc()).first()
    
    if not req:
        return jsonify({'success': False})
    
    return jsonify({
        'success': True,
        'status': req.status,
        'time': req.timestamp.isoformat()
    })

@app.route('/api/admin/sub_requests', methods=['GET'])
@admin_required
def get_sub_requests():
    from backend.models import SubscriptionRequest
    reqs = db.session.query(SubscriptionRequest).filter_by(status='PENDING').all()
    output = []
    for r in reqs:
        output.append({
            'id': r.id,
            'username': r.username,
            'upi_ref': r.upi_ref,
            'proof_url': f'/uploads/{r.proof_image}' if r.proof_image else None,
            'time': r.timestamp.strftime('%Y-%m-%d %H:%M')
        })
    return jsonify(output)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/admin/approve_sub', methods=['POST'])
@admin_required
def approve_sub():
    from backend.models import SubscriptionRequest
    data = request.json
    req = db.session.get(SubscriptionRequest, data['id'])
    if req:
        req.status = 'APPROVED'
        user = db.session.get(User, req.user_id)
        user.is_active = True
        user.expiry_date = datetime.now(timezone.utc) + timedelta(days=30)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/api/admin/kill_switch', methods=['POST'])
@admin_required
def toggle_kill_switch():
    if hasattr(app, 'trading_engine'):
        engine = app.trading_engine
        data = request.json
        if data.get('active'):
            engine.risk_manager.activate_kill_switch()
        else:
            engine.risk_manager.deactivate_kill_switch()
        return jsonify({'success': True, 'active': engine.risk_manager.kill_switch_active})
    return jsonify({'success': False, 'message': 'Engine not found'})

@app.route('/api/admin/reload_config', methods=['POST'])
@admin_required
def reload_config():
    if hasattr(app, 'trading_engine'):
        app.trading_engine.risk_manager.config = app.trading_engine.risk_manager.load_config()
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/api/user/risk-config', methods=['GET'])
@login_required
def get_user_risk_config():
    user = db.session.query(User).get(session['user_id'])
    if not user.config:
        new_cfg = AngelConfig(user_id=user.id)
        db.session.add(new_cfg)
        db.session.commit()
    
    return jsonify({
        'risk': {
            'total_capital': user.config.starting_capital or 100000.0,
            'max_daily_loss_pct': user.config.max_daily_loss_pct or 3.0,
            'risk_per_trade_pct': user.config.risk_per_trade_pct or 2.0
        },
        'strategy': {
            'min_confidence_score': user.config.min_confidence_score or 75
        }
    })

@app.route('/api/user/risk-config', methods=['POST'])
@login_required
def update_user_risk_config():
    try:
        user = db.session.query(User).get(session['user_id'])
        if not user.config:
            user.config = AngelConfig(user_id=user.id)
            db.session.add(user.config)
        
        data = request.json
        risk = data.get('risk', {})
        strat = data.get('strategy', {})
        
        user.config.starting_capital = float(risk.get('total_capital') or user.config.starting_capital or 100000.0)
        user.config.max_daily_loss_pct = float(risk.get('max_daily_loss_pct') or user.config.max_daily_loss_pct or 3.0)
        user.config.risk_per_trade_pct = float(risk.get('risk_per_trade_pct') or user.config.risk_per_trade_pct or 2.0)
        user.config.min_confidence_score = int(strat.get('min_confidence_score') or user.config.min_confidence_score or 75)
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

def daily_autologin_job():
    """Background task to login all users at 9:15 AM IST"""
    print("[*] Running Daily Auto-Login Job...")
    with app.app_context():
        users = db.session.query(User).filter_by(is_active=True).all()
        for user in users:
            if user.config and user.config.api_key:
                print(f"[*] Auto-logging in user: {user.username}")
                login_angel_one(user, app)

def schedule_autologin():
    """Simple thread-based scheduler for 9:15 AM IST"""
    def run():
        while True:
            # Check every minute
            now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
            if now.hour == 9 and now.minute == 15:
                daily_autologin_job()
                time.sleep(65) # Skip rest of the minute
            time.sleep(30)
    threading.Thread(target=run, daemon=True).start()

schedule_autologin()

@app.route('/api/shutdown', methods=['POST'])
@admin_required
def shutdown():
    os._exit(0)

# --- FRONTEND SERVING ---
FRONTEND_DIST = os.path.join(BASE_DIR, 'frontend', 'dist')

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    if path != "" and os.path.exists(os.path.join(FRONTEND_DIST, path)):
        return send_from_directory(FRONTEND_DIST, path)
    else:
        # Fallback to index.html for React routing
        if os.path.exists(os.path.join(FRONTEND_DIST, 'index.html')):
            return send_from_directory(FRONTEND_DIST, 'index.html')
        # Fallback if frontend is not built
        return jsonify({'status': 'online', 'service': 'AI Bot Trader API', 'message': 'Frontend not built. Run npm run build in frontend folder.'})

if __name__ == '__main__':
    # When running directly (development), use the Flask dev server
    # init_db() and start_scanner_locked() already ran above at module level
    app.run(host='0.0.0.0', port=8000, debug=False)
