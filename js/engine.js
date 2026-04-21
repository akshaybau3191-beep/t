/**
 * Elite Proprietary Trading Engine - Core Logic
 */

const TradingEngine = {
    totalCapital: 0,
    riskAmount: 0,
    maxDailyLoss: 0,
    currentDailyLoss: 0,
    tradesToday: 0,
    maxTradesPerDay: 3,
    confidenceThreshold: 75,
    executionMode: 'PAPER', // 'PAPER' or 'LIVE'
    activeTrade: null,
    indices: ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY'],
    
    // Self-Learning AI Weights
    weights: {
        trend: 30,
        momentum: 20,
        atr: 15,
        volume: 20,
        breakout: 15
    },
    
    // Initialize Engine with Capital
    initialize(capital) {
        this.totalCapital = parseFloat(capital);
        this.calculateRiskModel();
        this.maxDailyLoss = this.totalCapital * 0.10;
        this.loadLearningData();
        console.log(`Engine Initialized. Mode: ${this.executionMode}, Capital: ₹${this.totalCapital}`);
    },

    loadLearningData() {
        const savedWeights = localStorage.getItem('ai_weights');
        if (savedWeights) {
            this.weights = JSON.parse(savedWeights);
            console.log("AI Model: Loaded refined weights", this.weights);
        }
    },

    // Risk Model based on Capital brackets
    calculateRiskModel() {
        let riskPercent = 0;
        if (this.totalCapital <= 20000) {
            riskPercent = 0.08; // 8% avg of 5-10%
        } else if (this.totalCapital <= 100000) {
            riskPercent = 0.04; // 4% avg of 3-5%
        } else {
            riskPercent = 0.025; // 2.5% avg of 2-3%
        }
        this.riskAmount = this.totalCapital * riskPercent;
    },

    /**
     * Market Scanner Scoring Logic
     * Scans indices based on provided market data
     */
    scoreIndex(data) {
        let score = 0;
        
        // 1. Trend (EMA 21/50)
        if (data.ema21 > data.ema50 && data.price > data.ema21) score += this.weights.trend;
        else if (data.ema21 < data.ema50 && data.price < data.ema21) score += this.weights.trend;
        
        // 2. Momentum
        if (data.momentum > 70 || data.momentum < 30) score += this.weights.momentum;
        
        // 3. ATR Expansion
        if (data.atrRatio > 1.2) score += this.weights.atr;
        
        // 4. Volume Spike
        if (data.volumeRatio > 1.8) score += this.weights.volume;
        
        // 5. Breakout Structure
        if (data.isBreakout) score += this.weights.breakout;

        return score;
    },

    /**
     * Option Selection Logic
     */
    selectOption(index, type, price) {
        // Mock logic: choosing ATM strike
        const strike = Math.round(price / 50) * 50; 
        return {
            symbol: `${index} ${strike} ${type}`,
            type: type,
            strike: strike,
            premium: 100 // Placeholder premium
        };
    },

    /**
     * Stoploss Calculation (Premium Based)
     */
    calculateSL(premium, volatility) {
        // Min 10%, Max 25%
        let slPercent = 0.15; // Ideal 15-20%
        if (volatility > 2) slPercent = 0.20;
        
        const slAmount = premium * slPercent;
        return premium - slAmount;
    },

    /**
     * Target Calculation
     */
    calculateTarget(premium) {
        // Ideal 50-100%
        return premium + (premium * 0.70);
    },

    /**
     * Position Sizing
     * Qty = RISK_AMOUNT / (Premium - SL)
     */
    calculateQuantity(premium, sl) {
        const riskPerOption = premium - sl;
        let qty = Math.floor(this.riskAmount / riskPerOption);
        
        // Round to nearest lot size (Simplified)
        // Nifty: 50, BankNifty: 15, Finnifty: 40, Midcp: 75
        return qty;
    },

    /**
     * Trailing Stop Logic
     */
    getTrailingSL(currentPremium, entryPremium, currentSL) {
        const gainPercent = ((currentPremium - entryPremium) / entryPremium) * 100;
        
        if (gainPercent >= 100) return "PARTIAL_EXIT";
        if (gainPercent >= 60) return entryPremium + (entryPremium * 0.40);
        if (gainPercent >= 40) return entryPremium + (entryPremium * 0.20);
        if (gainPercent >= 20) return entryPremium; // SL to cost
        
        return currentSL;
    },

    /**
     * Early Exit Logic
     */
    shouldExitEarly(currentPremium, entryPremium, candlesPassed) {
        // If premium does not increase in 2 candles
        if (candlesPassed >= 2 && currentPremium <= entryPremium) return true;
        
        // If premium drops fast (e.g. 10% in 1 candle)
        // (Logic handled in tick update)
        
        return false;
    },

    /**
     * Self-Learning Algorithm
     * Analyzes trade results and optimizes weights
     */
    learn(tradeResult) {
        console.log("AI Learning: Analyzing individual trade result...", tradeResult);
        const { isWin, metrics } = tradeResult;
        
        const learningRate = 0.5;

        if (isWin) {
            if (metrics.isBreakout) this.weights.breakout += learningRate;
            if (metrics.volumeRatio > 2.0) this.weights.volume += learningRate;
            if (metrics.atrRatio > 1.5) this.weights.atr += learningRate;
        } else {
            if (metrics.isBreakout) this.weights.breakout -= learningRate;
            if (metrics.volumeRatio > 1.8) this.weights.volume -= learningRate;
        }

        this.normalizeWeights();
    },

    /**
     * Batch Learning Logic
     * Analyzes all trades from the day to perform optimized weight adjustment
     */
    batchLearn(history) {
        if (!history || history.length === 0) return;
        console.log(`AI Batch Learning: Processing ${history.length} trades from today.`);
        
        history.forEach(trade => {
            const isWin = trade.pnl > 0;
            const metrics = trade.metrics;
            const learningRate = 0.2; // Smaller rate for stable batch processing

            if (isWin) {
                if (metrics.isBreakout) this.weights.breakout += learningRate;
                if (metrics.volumeRatio > 2.0) this.weights.volume += learningRate;
                if (metrics.atrRatio > 1.5) this.weights.atr += learningRate;
            } else {
                if (metrics.isBreakout) this.weights.breakout -= learningRate;
                if (metrics.volumeRatio > 1.8) this.weights.volume -= learningRate;
            }
        });

        this.normalizeWeights();
        console.log("AI Model: Daily weights optimized.", this.weights);
    },

    normalizeWeights() {
        const total = Object.values(this.weights).reduce((a, b) => a + b, 0);
        for (let key in this.weights) {
            this.weights[key] = (this.weights[key] / total) * 100;
        }
        localStorage.setItem('ai_weights', JSON.stringify(this.weights));
    }
};

// Export or globalize
window.TradingEngine = TradingEngine;
