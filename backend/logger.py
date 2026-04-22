import os
import json
import csv
from datetime import datetime

class AuditLogger:
    def __init__(self, log_dir='logs'):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        self.trade_log_path = os.path.join(self.log_dir, 'trades.csv')
        self._init_trade_log()

    def _init_trade_log(self):
        if not os.path.exists(self.trade_log_path):
            with open(self.trade_log_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Timestamp', 'Symbol', 'Type', 'Qty', 'Price', 
                    'Confidence', 'Reason', 'Status', 'P&L'
                ])

    def log_trade(self, trade_data):
        """
        trade_data: { 'symbol', 'type', 'qty', 'price', 'confidence', 'reason', 'status', 'pnl' }
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # CSV Log
        with open(self.trade_log_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp, trade_data.get('symbol'), trade_data.get('type'),
                trade_data.get('qty'), trade_data.get('price'),
                trade_data.get('confidence'), trade_data.get('reason'),
                trade_data.get('status'), trade_data.get('pnl')
            ])
            
        # JSON Log (Detail per trade)
        json_path = os.path.join(self.log_dir, f"trade_{int(datetime.now().timestamp())}.json")
        with open(json_path, 'w') as f:
            json.dump({**trade_data, 'timestamp': timestamp}, f, indent=4)

    def log_event(self, event_type, message):
        log_path = os.path.join(self.log_dir, 'events.log')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_path, 'a') as f:
            f.write(f"[{timestamp}] {event_type.upper()}: {message}\n")
