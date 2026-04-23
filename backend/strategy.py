import pandas as pd
import numpy as np

class EliteStrategyManager:
    def __init__(self, risk_manager):
        self.risk_manager = risk_manager

    def analyze(self, symbol, ltp_data, candles_1m, candles_5m, logger=None):
        """Elite Consensus Scoring: 1m/5m Alignment + OI + Orderbook"""
        score = 0
        factors = []
        
        def log(msg):
            if logger: logger(f"   [STRATEGY] {msg}")

        # 1. PRICE ACTION PILLAR (40 Points)
        # Use 1m for entry precision and 5m for trend confirmation
        if candles_1m and len(candles_1m) > 20 and candles_5m and len(candles_5m) > 10:
            df1 = self._prepare_df(candles_1m)
            df5 = self._prepare_df(candles_5m)
            
            # A. Trend Alignment (20 pts)
            trend_1m = df1['close'].iloc[-1] > df1['ema21'].iloc[-1]
            trend_5m = df5['close'].iloc[-1] > df5['ema21'].iloc[-1]
            if trend_1m and trend_5m:
                score += 20
                factors.append("Multi-TF Trend: 1m & 5m Alignment (Bullish)")
            
            # B. Momentum / RSI (10 pts)
            rsi = self._calculate_rsi(df1['close'])
            if 55 < rsi < 70:
                score += 10
                factors.append(f"Momentum: RSI at {int(rsi)} (Healthy Bullish)")
            
            # C. VWAP Support (10 pts)
            vwap = self._calculate_vwap(df1)
            if df1['close'].iloc[-1] > vwap:
                score += 10
                factors.append("Support: Price above VWAP")

        # 2. DATA PILLAR: OI & VOLUME (30 Points)
        volume = float(ltp_data.get('volume', 0))
        oi = float(ltp_data.get('oi', 0))
        
        # Volume Surge detection
        if candles_1m:
            avg_vol = df1['volume'].tail(10).mean()
            if volume > avg_vol * 2.0:
                score += 15
                factors.append("Volume: Institutional Surge detected")
        
        # OI Accumulation (Angel One gives current OI)
        # In a real setup, we'd compare this with previous tick OI
        if oi > 0:
            score += 15 # Baseline for presence of OI
            factors.append(f"Liquidity: Active OI at {int(oi)}")

        # 3. PRESSURE PILLAR: ORDERBOOK (30 Points)
        buy_qty = float(ltp_data.get('totalBuyQty', 0))
        sell_qty = float(ltp_data.get('totalSellQty', 0))
        
        if sell_qty > 0:
            ratio = buy_qty / sell_qty
            if ratio > 1.5:
                score += 20
                factors.append(f"Pressure: Strong Demand (Buy/Sell Ratio {ratio:.1f}x)")
            elif ratio > 2.5:
                score += 30
                factors.append("Pressure: EXTREME Demand (Breakout Imminent)")

        # FINAL VERDICT
        status = "REJECT"
        if score >= 85: status = "STRONG_BUY"
        elif score >= 70: status = "BUY"
        
        return {
            'score': score,
            'status': status,
            'factors': factors,
            'ltp': float(ltp_data.get('ltp', 0))
        }

    def _prepare_df(self, candles):
        df = pd.DataFrame(candles, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
        return df

    def _calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs)).iloc[-1]

    def _calculate_vwap(self, df):
        tp = (df['high'] + df['low'] + df['close']) / 3
        return (tp * df['volume']).cumsum() / df['volume'].cumsum().iloc[-1]
