import pandas as pd
import numpy as np

class StrategyManager:
    def __init__(self, risk_manager):
        self.risk_manager = risk_manager

    def analyze_option(self, candles, data, info, index_ltp):
        """Advanced Option Scalping Strategy with Fallback Logic"""
        strength = 0
        reasons = []
        
        # 1. Base Info
        oi = int(data.get('oi', 0))
        volume = int(data.get('volume', 0))
        total_buy_qty = int(data.get('totalBuyQty', 0))
        total_sell_qty = int(data.get('totalSellQty', 0))
        ltp = float(data.get('ltp', 0))

        # 2. Historical Analysis (If candles available)
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
                reasons.append("Above EMA9")
            if last['ema9'] > last['ema21']:
                strength += 20
                reasons.append("Bullish EMA Cross")
            if last['close'] > last['vwap']:
                strength += 20
                reasons.append("Above VWAP")
            
            # Volume Trend
            avg_vol = df['volume'].tail(5).mean()
            if last['volume'] > avg_vol * 1.2:
                strength += 20
                reasons.append("Volume Surge")
        else:
            # Fallback if no historical data: use orderbook and index correlation
            # If Index is trending (we'd need index EMA here but let's stick to orderbook)
            reasons.append("Historical Data N/A")

        # 3. Real-time Orderbook Bias (Works without candles)
        if total_buy_qty > total_sell_qty * 1.2:
            strength += 30
            reasons.append("Strong Orderbook Buy Bias")
        elif total_buy_qty > total_sell_qty * 1.05:
            strength += 15
            reasons.append("Orderbook Buy Bias")

        # 4. Volume Activity
        if volume > 50000:
            strength += 10
            reasons.append("High Liquidity")

        return {
            'price': ltp,
            'oi': oi,
            'volume': volume,
            'signal_strength': min(100, strength),
            'reason': ", ".join(reasons)
        }
