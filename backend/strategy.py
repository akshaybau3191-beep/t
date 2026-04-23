import pandas as pd
import numpy as np

class EliteStrategyManager:
    def __init__(self, risk_manager):
        self.risk_manager = risk_manager

    def analyze(self, symbol, ltp_data, candles_1m, candles_5m, logger=None):
        """Elite Consensus Scoring: Institutional Volume + OI Divergence + Pressure"""
        score = 0
        factors = []
        
        def log(msg):
            if logger: logger(f"   [STRATEGY] {msg}")

        ltp = float(ltp_data.get('ltp', 0))
        if ltp < 10: return {'score': 0, 'status': 'REJECT', 'factors': ['Price too low (Theta Risk)'], 'ltp': ltp}

        # 1. PRICE ACTION PILLAR (35 Points)
        if candles_1m and len(candles_1m) > 20 and candles_5m and len(candles_5m) > 10:
            df1 = self._prepare_df(candles_1m)
            df5 = self._prepare_df(candles_5m)
            
            # Trend Alignment (15 pts)
            trend_1m = df1['close'].iloc[-1] > df1['ema21'].iloc[-1]
            trend_5m = df5['close'].iloc[-1] > df5['ema21'].iloc[-1]
            if trend_1m and trend_5m:
                score += 15
                factors.append("Multi-TF Trend: 1m & 5m Bullish Alignment")
            
            # Momentum (10 pts)
            rsi = self._calculate_rsi(df1['close'])
            if 60 < rsi < 75:
                score += 10
                factors.append(f"Momentum: RSI Strong at {int(rsi)}")
            
            # VWAP Support (10 pts)
            vwap = self._calculate_vwap(df1)
            if df1['close'].iloc[-1] > vwap:
                score += 10
                factors.append("Support: Price above VWAP")

        # 2. INSTITUTIONAL DATA PILLAR (35 Points)
        volume = float(ltp_data.get('volume', 0))
        oi = float(ltp_data.get('oi', 0))
        
        # OI Accumulation vs Volume (20 pts)
        # Ratio of OI to Volume indicates 'Hold' vs 'Trade'
        if volume > 0:
            oi_vol_ratio = oi / volume
            if oi_vol_ratio > 0.5:
                score += 20
                factors.append(f"Sentiment: High OI/Vol Ratio ({oi_vol_ratio:.1f}) - Strong Holding")
        
        # Volume Surge (15 pts)
        if candles_1m:
            df1 = self._prepare_df(candles_1m)
            avg_vol = df1['volume'].tail(5).mean()
            if volume > avg_vol * 1.5:
                score += 15
                factors.append("Volume: Institutional Spike detected")

        # 3. BID-ASK PRESSURE PILLAR (30 Points)
        buy_qty = float(ltp_data.get('totalBuyQty', 0))
        sell_qty = float(ltp_data.get('totalSellQty', 0))
        
        if sell_qty > 0:
            ratio = buy_qty / sell_qty
            if ratio > 2.0:
                score += 30
                factors.append(f"Pressure: EXTREME Demand ({ratio:.1f}x Buying)")
            elif ratio > 1.3:
                score += 15
                factors.append(f"Pressure: Bullish Demand ({ratio:.1f}x Buying)")

        # FINAL VERDICT
        status = "REJECT"
        if score >= 85: status = "STRONG_BUY"
        elif score >= 70: status = "BUY"
        
        return {
            'score': score,
            'status': status,
            'factors': factors,
            'ltp': ltp
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
