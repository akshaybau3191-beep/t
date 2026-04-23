import pandas as pd
import numpy as np

class StrategyManager:
    def __init__(self, risk_manager):
        self.risk_manager = risk_manager

    def analyze_option(self, candles, data, info, index_ltp, logger=None):
        """Master AI Strategy: Price Action, OI, Volume & Volatility"""
        strength = 0
        reasons = []
        
        def log(msg):
            if logger: logger(f"   [AI-LOG] {msg}")

        # 1. Base Data Extraction
        oi = int(data.get('oi', 0))
        oi_change = int(data.get('oi_change', 0)) # Angel provides this in FULL data
        volume = int(data.get('volume', 0))
        buy_qty = int(data.get('totalBuyQty', 0))
        sell_qty = int(data.get('totalSellQty', 0))
        ltp = float(data.get('ltp', 0))

        # 2. Price Action & Trend Analysis
        if candles and len(candles) > 20:
            df = pd.DataFrame(candles, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            # Indicators
            df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
            df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
            tp = (df['high'] + df['low'] + df['close']) / 3
            df['vwap'] = (tp * df['volume']).cumsum() / df['volume'].cumsum()
            
            last = df.iloc[-1]
            prev = df.iloc[-2]

            # A. Trend Pillar (20 pts)
            if last['close'] > last['ema9'] and last['ema9'] > last['ema21']:
                strength += 20
                log("Trend: Strong Bullish Alignment (Price > EMA9 > EMA21)")
            
            # B. Price Action / Candlesticks (20 pts)
            if last['close'] > prev['high']: # Bullish Breakout
                strength += 10
                log("Price Action: Recent High Breakout detected")
            if last['close'] > last['open'] and prev['close'] < prev['open'] and last['close'] > prev['open']:
                strength += 10
                log("Candlestick: Bullish Engulfing Pattern found")

            # C. Volume Pillar (15 pts)
            avg_vol = df['volume'].tail(10).mean()
            if last['volume'] > avg_vol * 1.8:
                strength += 15
                log(f"Volume: Institutional Surge ({int(last['volume'])} vs {int(avg_vol)} avg)")
        
        # 3. OI Pillar (20 pts)
        if oi_change > 0:
            strength += 10
            log(f"OI: Positive buildup (+{oi_change} contracts)")
        if buy_qty > sell_qty * 1.5:
            strength += 10
            log("Orderbook: Heavy Buy Pressure")

        # 4. Volatility Pillar (SL/TP Calculation)
        # Calculate Dynamic SL based on 2% risk or ATR (if available)
        sl_pct = 0.10 # Default 10%
        tp_pct = 0.20 # Default 20%
        
        final_strength = min(100, strength)
        signal = 'BUY' if final_strength >= 50 else 'WAIT'

        return {
            'price': ltp,
            'oi': oi,
            'signal_strength': final_strength,
            'signal': signal,
            'sl': round(ltp * (1 - sl_pct), 2),
            'tp': round(ltp * (1 + tp_pct), 2),
            'reason': ", ".join(reasons)
        }
