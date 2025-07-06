import pandas as pd
import backtrader as bt

###Step 1: Data Preparation

# Assume data is in a CSV file 'ES_tick_data.csv'
# In a real scenario, this would come from a live feed or a historical data provider, like the Polygon.io, Tickdata.com and Databento.
def load_and_prepare_data(filepath):
    """
    Loads and prepares tick data for backtesting.
    """
    df = pd.read_csv(filepath)
    
    # Ensure timestamp is in the correct format
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.ffill(inplace=True)    # Forward-fill to handle moments where only a trade or a quote update occurs
    df.dropna(inplace=True)     # Drop any remaining NaNs
 
    print("Data prepared. Sample:")
    print(df.head())
    return df

# Example usage for ES futures
es_data = load_and_prepare_data('ES_tick_data.csv')

###Step 2: Define and Code the Trading Rules
class OrderImbalanceStrategy(bt.Strategy):
    params = (
        ('imbalance_threshold', 50), # From the report: 50 lots difference 
        ('hold_ticks', 5),           # From the report: minimum hold time
    )

    def __init__(self):
        # Keep track of the number of ticks we've held a position
        self.ticks_held = 0

    def next(self):
        # Using .iloc[0] to access the current tick's data in a pandas-like structure
        current_bid_size = self.data.bid_size[0]
        current_ask_size = self.data.ask_size[0]

        # Calculate the order book imbalance
        imbalance = current_bid_size - current_ask_size

        # --- ENTRY LOGIC ---
        if not self.position:
            if imbalance > self.params.imbalance_threshold:
                # Strong buying pressure, go long
                self.buy(size=1) # Trading 1 lot to minimize price impact
                self.ticks_held = 0
            elif imbalance < -self.params.imbalance_threshold:
                # Strong selling pressure, go short
                self.sell(size=1)
                self.ticks_held = 0
        
        # --- EXIT LOGIC ---
        elif self.position:
            self.ticks_held += 1
            if self.ticks_held >= self.params.hold_ticks:
                self.close() # Close position after holding for the minimum duration

###Step 3: Event-Based Backtesting
# 1. Create a Cerebro instance (the backtesting engine)
cerebro = bt.Cerebro()

# 2. Add the custom data feed for ES futures
class CustomFuturesData(bt.feeds.PandasData):
    """
    Custom data feed for futures tick data that includes Level 1 bid/ask
    information. It bypasses the standard OHLC format to provide direct
    access to bid/ask prices and sizes for HFT strategies.
    
    This approach is based on backtrader's ability to replace the default
    data line hierarchy by setting `linesoverride = True`.
    """
    
    # Use linesoverride to replace the default OHLCV lines [T12](2)
    linesoverride = True

    # Define the new data lines for our feed. 
    # The 'lines' tuple adds new data streams to the strategy.
    lines = ('bid_price', 'ask_price', 'bid_size', 'ask_size',)

    # Define the parameters for mapping DataFrame columns to the lines.
    # A value of -1 indicates that a particular line (e.g., 'open') is not used.
    # The keys are the backtrader line names, and the values are the column names
    # in the pandas DataFrame.
    params = (
        ('datetime', None),         # Use the DataFrame's index for datetime [T11](1)
        ('open', -1),               # Not used
        ('high', -1),               # Not used
        ('low', -1),                # Not used
        ('close', 'last_price'),    # Map 'close' to the 'last_price' column [AI KNOWLEDGE]({})
        ('volume', -1),             # Not used
        ('openinterest', -1),       # Not used
        ('bid_price', 'bid_price'), # Map 'bid_price' line to 'bid_price' column
        ('ask_price', 'ask_price'), # Map 'ask_price' line to 'ask_price' column
        ('bid_size', 'bid_size'),   # Map 'bid_size' line to 'bid_size' column
        ('ask_size', 'ask_size'),   # Map 'ask_size' line to 'ask_size' column
    )

data_feed = CustomFuturesData(dataname=es_data)
cerebro.adddata(data_feed)

# 3. Add the strategy
cerebro.addstrategy(OrderImbalanceStrategy)

# 4. Set initial capital
cerebro.broker.setcash(200000.0) # Based on the report's example

# 5. Set commissions
cerebro.broker.setcommission(commission=2.5, margin=2000, mult=50.0) # Example for ES

# 6. Add analyzers for performance evaluation
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

# 7. Run the backtest
print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
results = cerebro.run()
print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue()

###Step 4: Performance Evaluation
This code would run after 'cerebro.run()'
strat = results[0]

print('--- Performance Metrics ---')
print(f"Sharpe Ratio: {strat.analyzers.sharpe.get_analysis()['sharperatio']:.2f}")
print(f"Max Drawdown: {strat.analyzers.drawdown.get_analysis().max.drawdown:.2f}%")

trade_analysis = strat.analyzers.trades.get_analysis()
if trade_analysis.total.total > 0:
    win_rate = (trade_analysis.won.total / trade_analysis.total.total) * 100
    print(f"Total Trades: {trade_analysis.total.total}")
    print(f"Win Rate: {win_rate:.2f}%")

# The report's backtest showed a 280% return, which is exceptionally high and
# highlights the potential gap between idealized simulations and live trading outcomes.
# A thorough analysis would involve running this strategy on GC, ZN, and ES
# across different time periods to test its robustness.

