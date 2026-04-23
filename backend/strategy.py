import pandas as pd
import numpy as np

class EliteStrategyManager:
    def __init__(self, risk_manager):
        self.risk_manager = risk_manager

    def analyze(self, symbol, ltp_data, candles_1m, candles_5m, candles_3m=None, logger=None):
        """Institutional Quantitative Scorer: TF-Alignment + OI Sentiment + Book Pressure"""
        score = 0
        factors = []
        
        ltp = float(ltp_data.get('ltp', 0))
        if ltp < 10: return {'score': 0, 'status': 'REJECT', 'factors': ['Price too low (Theta Risk)'], 'ltp': ltp}

        # 1. MULTI-TIMEFRAME TREND (30 Points)
        if candles_1m and candles_5m and len(candles_1m) > 20:
            df1 = self._prepare_df(candles_1m)
            df5 = self._prepare_df(candles_5m)
            
            # Trend Check (1m/5m)
            bullish_1m = df1['close'].iloc[-1] > df1['ema21'].iloc[-1]
            bullish_5m = df5['close'].iloc[-1] > df5['ema21'].iloc[-1]
            
            if bullish_1m and bullish_5m:
                score += 20
                factors.append("Trend: 1m/5m Alignment (Bullish)")
                
                # Optional 3m kicker
                if candles_3m:
                    df3 = self._prepare_df(candles_3m)
                    if df3['close'].iloc[-1] > df3['ema21'].iloc[-1]:
                        score += 10
                        factors.append("Trend: 3m Confirmation (Strong)")

        # 2. INSTITUTIONAL DATA PILLAR (40 Points)
        volume = float(ltp_data.get('volume', 0))
        oi = float(ltp_data.get('oi', 0))
        
        # A. OI Sentiment (20 pts)
        # Higher OI/Vol ratio means institutions are holding, not just flipping
        if volume > 0:
            oi_vol_ratio = oi / volume
            if oi_vol_ratio > 0.8:
                score += 20
                factors.append(f"Sentiment: Extreme OI Holding (Ratio: {oi_vol_ratio:.1f})")
            elif oi_vol_ratio > 0.4:
                score += 10
                factors.append(f"Sentiment: Moderate Institutional Interest")

        # B. Volume RVOL (20 pts)
        if candles_1m:
            df1 = self._prepare_df(candles_1m)
            avg_vol = df1['volume'].tail(10).mean()
            if volume > avg_vol * 2.0:
                score += 20
                factors.append("Volume: RVol Spike (2x Average)")
            elif volume > avg_vol * 1.5:
                score += 10
                factors.append("Volume: Moderate Surge")

        # 3. BID-ASK PRESSURE (30 Points)
        buy_qty = float(ltp_data.get('totalBuyQty', 0))
        sell_qty = float(ltp_data.get('totalSellQty', 0))
        
        if sell_qty > 0:
            ratio = buy_qty / sell_qty
            if ratio > 2.5:
                score += 30
                factors.append(f"Pressure: EXTREME Demand ({ratio:.1f}x Buying)")
            elif ratio > 1.5:
                score += 15
                factors.append(f"Pressure: Strong Demand ({ratio:.1f}x Buying)")

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
