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
        Calculate lots based on total capital: Lots = Capital / (Price * LotSize)
        Round down to lower integer.
        """
        total_cap = user_config.starting_capital or 100000
        
        # CUSTOM LOT SIZES
        lot_sizes = {
            'NIFTY': 65,
            'BANKNIFTY': 30
        }
        market_lot = lot_sizes.get(index, 65)
        
        if option_price <= 0: return 0
        
        # Formula: Lot = Capital / (LTP * LotSize)
        price_per_lot = option_price * market_lot
        
        if price_per_lot > total_cap:
            print(f"[*] Insufficient capital for {index} (Price/Lot: ₹{price_per_lot:.0f}, Cap: ₹{total_cap:.0f})")
            return 0 # 0.8 lot case
            
        num_lots = int(total_cap / price_per_lot)
        return num_lots * market_lot # Return total quantity

    def activate_kill_switch(self):
        self.kill_switch_active = True
        print("[!!!] KILL SWITCH ACTIVATED [!!!]")

    def deactivate_kill_switch(self):
        self.kill_switch_active = False
        print("[*] Kill Switch Deactivated.")
