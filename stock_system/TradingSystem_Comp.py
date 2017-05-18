###################################################################################################
# Trading System replication:
#
###################################################################################################
import numpy as np
from minepy import MINE
from sklearn.feature_selection import RFE
import inspect
import talib
from stock_system.TradingSystem import TradingSystem
from stock_system import TA, ModelUtils


class TradingSystem_Comp(TradingSystem):
    '''
    Parent class for trading systems
    '''
    def __init__(self):
        TradingSystem.__init__(self)
        self.df = None  # The source data frame - the X features
        self.target = None  # The y label target, generated by a system algorithm from X data
        self.features = []  # list of X feature columns for the trading system and implementing model

    def preprocess_data(self, data):
        '''
        Perform any data preprocessing steps such as normalizing, smoothing,
        remove correlated columns, etc
        '''
        df = data.copy()


        #df = TA.run_techicals(df)

        # normal and smoothed Price series
        opn = df['open']
        high = df['high']
        low = df['low']
        close = df['close']
        volume = df['volume'].astype(float)

        # df = TA.run_exp_smooth(df, alpha=.5)
        # opn_sm = df['exp_smooth_open']
        # high_sm = df['exp_smooth_high']
        # low_sm = df['exp_smooth_low']
        # close_sm = df['exp_smooth_close']
        # volume_sm = df['exp_smooth_volume']

        # Can play with short and long time preiods...
        r5 = df.close.rolling(window=5)
        r10 = df.close.rolling(window=10)
        r20 = df.close.rolling(window=20)
        r30 = df.close.rolling(window=30)

        # from article post
        df['daily_return'] = close - np.roll(close, 1)
        df['log_daily_return'] = np.log(df['daily_return'] + 1 - min(df['daily_return']))
        df['log_close'] = np.log(close)
        df['mean_log_close_5'] = df['log_close'].rolling(window=5).mean()
        # daily_p = history(bar_count=100, frequency='1d', field='price')
        # daily_ret = daily_p.pct_change()
        # daily_log = np.log1p(daily_ret)
        # daily_log_mean = pd.rolling_mean(daily_log, 5)
        # print daily_log_mean.tail(5)

        df['apc5'] = df['mean_log_close_5'] / talib.ATR(high.values, low.values, df['log_close'].values, timeperiod=100)
        df['atr14'] = talib.ATR(high.values, low.values, close.values, timeperiod=14)
        df['ATRrat3'] = talib.ATR(high.values, low.values, close.values, timeperiod=3) / talib.ATR(high.values, low.values, close.values, timeperiod=21)
        df['ATRrat10'] = talib.ATR(high.values, low.values, close.values, timeperiod=10) / talib.ATR(high.values, low.values, close.values, timeperiod=50)
        df['deltaATRrat33'] = df['ATRrat3'] - np.roll(df['ATRrat3'], 3)
        df['deltaATRrat310'] = df['ATRrat3'] - np.roll(df['ATRrat3'], 10)
        df['mom10'] = talib.MOM(close.values, timeperiod=10)
        df['mom3'] = talib.MOM(close.values, timeperiod=3)

        upperband, middleband, lowerband = talib.BBANDS(close.values, timeperiod=3, nbdevup=2, nbdevdn=2, matype=0)
        df['bWidth3'] = upperband - lowerband
        upperband, middleband, lowerband = talib.BBANDS(close.values, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
        df['bWidth20'] = upperband - lowerband
        df['deltabWidth33'] = df['bWidth3'] - np.roll(df['bWidth3'], 3)
        df['deltabWidth310'] = df['bWidth3'] - np.roll(df['bWidth3'], 10)

        linreg_preiod = 20
        df['linreg'] = talib.LINEARREG(close.values, timeperiod=linreg_preiod)
        #df['linreg'] = pd.stats.ols.MovingOLS(y=close, x=pd.Series(range(len(df.index))), window_type='rolling', window=100, intercept=True)
        slope = talib.LINEARREG_SLOPE(close.values, timeperiod=linreg_preiod)
        intercept = talib.LINEARREG_INTERCEPT(close.values, timeperiod=linreg_preiod)
        #df['linreg_cast'] = intercept + close * slope  # This is incorrect
        df['linreg_cast'] = df['linreg'] + (df['linreg'] - np.roll(df['linreg'], 1))
        df['stdClose20'] = r20.std()

        df['price_var_ratio'] = r10.var() / r30.var()
        df['deltaPVR5'] = df['price_var_ratio'] - np.roll(df['price_var_ratio'], 5)

        df['hurst'] = TA.hurst(close)

        df['roc'] = TA.rate_of_change(close, 1)
        df['roc_d'] = TA.discrete_series_pos_neg(df['roc'])
        df['rsi'] = talib.RSI(close.values, timeperiod=14)
        df['rsi_d'] = TA.continuous_to_discrete_w_bounds(df['rsi'], 30,70)
        df['willr'] = talib.WILLR(high.values, low.values, close.values, timeperiod=14)
        df['obv'] = talib.OBV(close.values, volume.values)
        df['stok'], df['stod'] = talib.STOCH(high.values, low.values, close.values, fastk_period=5, slowk_period=3,
                                             slowk_matype=0, slowd_period=3, slowd_matype=0)

        # Part 2
        df['mom3'] = talib.MOM(close.values, timeperiod=3)
        df['deltabWidth310'] = df['bWidth3'] - np.roll(df['bWidth3'], 10)
        df['atr7'] = talib.ATR(high.values, low.values, close.values, timeperiod=7)
        df['ATRrat1020'] = talib.ATR(high.values, low.values, close.values, timeperiod=10) / talib.ATR(high.values, low.values, close.values, timeperiod=20)
        df['ATRrat10100'] = talib.ATR(high.values, low.values, close.values, timeperiod=10) / talib.ATR(high.values, low.values, close.values, timeperiod=100)

        # Impute - delete rows with Nan and null.  Will be the first several rows
        for name in df.columns:
            df = df[df[name].notnull()]

        df.pop('date')
        df.pop('symbol')
        # Normalize everything
        # df2 = (df - df.mean())/df.std()  # Z-score
        # or to max-min
        df2 = (df-df.min())/(df.max()-df.min())
        # - TODO a rolling 50 period window of normalizing, rather than the whole df.  rolling.apply

        self.df = df

        return self.df


    def get_features(self):
        # self.features = ['apc5', 'ATRrat3', 'deltaATRrat33', 'mom10', 'bWidth3', 'deltabWidth33',
        #                  'linreg_cast', 'price_var_ratio', 'deltaPVR5', 'hurst']
        #self.features = ['roc', 'stok', 'rsi', 'obv', 'willr']
        #self.features = ['price_var_ratio', 'deltaPVR5', 'mom3', 'ATRrat3']
        self.features = ['deltabWidth310', 'atr7', 'ATRrat1020', 'mom3', 'ATRrat10100']
        # Oscilators
        # x_osc = ['rsi', 'cci', 'stod', 'stok', 'willr']
        # x_oscd_cols = ['rsi_d', 'cci_d', 'stod_d', 'stok_d', 'willr_d']
        # # MAs
        # x_ma_cols = ['sma20', 'sma50', 'sma200', 'wma10', 'macd_d']
        # x_all_dscrete_cols = ['roc_d', 'rsi_d', 'cci_d', 'stod_d', 'stok_d', 'willr_d', 'mom_d']
        # #x_cols = ['roc', 'rsi', 'willr', 'obv', 'stok']#'mom', , 'cci',  'stod', 'macd', 'sma', 'sma50', 'wma']
        # #x_cols = ['roc']
        # x_cols = x_all_dscrete_cols + x_ma_cols
        return self.features

    def feature_selection(self):
        return TradingSystem.feature_selection(self)


    def generate_target(self):
        '''
        Trading system goes here.
        This runs the trading system on the training data to generate the y label.

        **** CAVEAT ****
        If target is price change over n days, you need to shift the y label target
        by n days (at least one day) to ensure no future leak.

        Returns a dataframe with the y label column, ready to use in a model for fit and predict.
        '''
        if self.df is None:
            print 'This trading system has no data.  Call preprocess_data first.'
            return

        # Target is a one-day price change
        days_ahead = -1
        self.df['gain_loss'] = np.roll(self.df['close'], days_ahead) - self.df['close']
        self.df['y_true'] = (self.df['gain_loss'] >= 0).astype(int)

        # Drop the last row becaue of the shift by 1 - it puts the first to the last
        # Probably needs to change
        self.df = self.df[:-1]

        return self.df
