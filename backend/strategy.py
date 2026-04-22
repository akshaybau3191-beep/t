class StrategyManager:
    def __init__(self, risk_manager):
        self.risk_manager = risk_manager

    def analyze_option(self, candles, data, info, index_ltp):
        """Advanced Option Scalping Strategy"""
        if not candles: return {'signal_strength': 0}
        
        df = pd.DataFrame(candles, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        
        # 1. Indicators: EMA(9, 21) and VWAP
        df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
        
        tp = (df['high'] + df['low'] + df['close']) / 3
        df['vwap'] = (tp * df['volume']).cumsum() / df['volume'].cumsum()
        
        last = df.iloc[-1]
        
        oi = int(data.get('oi', 0))
        volume = int(data.get('volume', 0))
        total_buy_qty = int(data.get('totalBuyQty', 0))
        total_sell_qty = int(data.get('totalSellQty', 0))
        
        strength = 0
        reasons = []

        # 2. Strategy Logic: EMA/VWAP Alignment
        if last['close'] > last['ema9'] > last['ema21'] and last['close'] > last['vwap']:
            strength += 50
            reasons.append("EMA/VWAP Bullish Alignment")
        
        # 3. Orderbook Bias
        if total_buy_qty > total_sell_qty * 1.3:
            strength += 30
            reasons.append("Strong Orderbook Buy Bias")
            
        # 4. Volume Spike
        if volume > 10000:
            strength += 20
            reasons.append("Volume Breakout")

        return {
            'price': float(data.get('ltp', 0)),
            'oi': oi,
            'volume': volume,
            'signal_strength': strength,
            'reason': ", ".join(reasons)
        }
