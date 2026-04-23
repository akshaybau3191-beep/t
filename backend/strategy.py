import pandas as pd
import numpy as np

class StrategyManager:
    def __init__(self, risk_manager):
        self.risk_manager = risk_manager

    def analyze_option(self, candles, data, info, index_ltp, logger=None):
        """Advanced Option Scalping Strategy with Step-by-Step Reporting"""
        strength = 0
        reasons = []
        
        def log(msg):
            if logger: logger(f"   [AI] {msg}")

        # 1. Base Info
        oi = int(data.get('oi', 0))
        volume = int(data.get('volume', 0))
        total_buy_qty = int(data.get('totalBuyQty', 0))
        total_sell_qty = int(data.get('totalSellQty', 0))
        ltp = float(data.get('ltp', 0))

        # 2. Historical Analysis
        if candles and len(candles) > 20:
            df = pd.DataFrame(candles, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
            df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
            tp = (df['high'] + df['low'] + df['close']) / 3
            df['vwap'] = (tp * df['volume']).cumsum() / df['volume'].cumsum()
            
            last = df.iloc[-1]
            if last['close'] > last['ema9']:
                strength += 20
                reasons.append("Bullish Trend (Above EMA9)")
                log("Confirmed Bullish Trend (Price > EMA9)")
            
            if last['ema9'] > last['ema21']:
                strength += 20
                reasons.append("Golden EMA Crossover")
                log("EMA Crossover Detected (+ve Momentum)")
            
            if last['close'] > last['vwap']:
                strength += 20
                reasons.append("Institutional Support (Above VWAP)")
                log("Trading Above VWAP (Institutional Buy Zone)")
            
            # Volume Trend
            avg_vol = df['volume'].tail(5).mean()
            if last['volume'] > avg_vol * 1.5:
                strength += 20
                reasons.append("Institutional Volume Inflow")
                log(f"Volume Surge Detected ({int(last['volume'])} vs avg {int(avg_vol)})")
        else:
            log("Wait: Accumulating historical candles for precision...")

        # 3. Real-time Orderbook Bias
        if total_buy_qty > total_sell_qty * 1.5:
            strength += 30
            reasons.append("Heavy Buy Orderbook Pressure")
            log(f"Orderbook: Strong Buy Bias ({total_buy_qty} vs {total_sell_qty})")
        elif total_buy_qty > total_sell_qty * 1.1:
            strength += 15
            log("Orderbook: Moderate Buy Interest")

        # 4. Liquidity Check
        if volume > 100000:
            strength += 10
            log("Liquidity: High (Good for fast entry/exit)")

        final_strength = min(100, strength)
        signal = 'BUY' if final_strength >= 50 else 'WAIT'
        
        return {
            'price': ltp,
            'oi': oi,
            'volume': volume,
            'signal_strength': final_strength,
            'signal': signal,
            'reason': ", ".join(reasons)
        }
