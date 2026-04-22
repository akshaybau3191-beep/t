import json
import os
from datetime import date

class RiskManager:
    def __init__(self, config_path='config.json'):
        self.config_path = config_path
        self.config = self.load_config()
        self.kill_switch_active = False
        
    def load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Error loading risk config: {e}")
            return {}

    def can_trade(self, user_config, current_stats):
        """
        Check if trading is allowed based on user-specific limits.
        user_config: AngelConfig model object
        current_stats: { 'daily_pnl': float, 'trades_count': int }
        """
        if self.kill_switch_active:
            return False, "Global Kill Switch Active"
            
        total_cap = user_config.starting_capital or 100000
        
        # 1. Daily Loss Limit
        max_loss = (user_config.max_daily_loss_pct / 100) * total_cap
        if current_stats.get('daily_pnl', 0) <= -max_loss:
            return False, f"Daily Loss Limit Reached: ₹{current_stats['daily_pnl']}"
            
        # 2. Daily Profit Target (Keep global or add to model if needed)
        # For now, use a fixed 5% or similar if not in model
        max_profit = 0.05 * total_cap 
        if current_stats.get('daily_pnl', 0) >= max_profit:
            return False, f"Daily Profit Target Reached: ₹{current_stats['daily_pnl']}"
            
        return True, "Ready"

    def calculate_lot_size(self, user_config, index, option_price):
        """
        Calculate lots based on user's risk per trade pct.
        """
        total_cap = user_config.starting_capital or 100000
        risk_amt = (user_config.risk_per_trade_pct / 100) * total_cap
        
        # Lot sizes for Angel One (Standard)
        lot_sizes = {'NIFTY': 50, 'BANKNIFTY': 15, 'FINNIFTY': 40}
        lot_size = lot_sizes.get(index, 50)
        
        if option_price <= 0: return 0
        
        # Max quantity we can buy with risk amount
        # In scalping, risk_amt often represents the absolute loss we can take on the trade.
        # But here we use it to limit exposure.
        max_qty = int(risk_amt / option_price)
        
        # Round down to nearest lot
        lots = max_qty // lot_size
        return max(1, lots) * lot_size # Minimum 1 lot

    def activate_kill_switch(self):
        self.kill_switch_active = True
        print("[!!!] KILL SWITCH ACTIVATED [!!!]")

    def deactivate_kill_switch(self):
        self.kill_switch_active = False
        print("[*] Kill Switch Deactivated.")
