
import QuantLib as ql
import numpy as np
from tsfin.constants import CALENDAR, MATURITY_DATE, \
    DAY_COUNTER, EXERCISE_TYPE, OPTION_TYPE, STRIKE_PRICE, UNDERLYING_INSTRUMENT, OPTION_CONTRACT_SIZE
from tsfin.base.instrument import default_arguments
from tsfin.base import Instrument, to_ql_option_type, to_ql_date, conditional_vectorize, \
    to_ql_calendar, to_ql_day_counter, to_datetime


def option_exercise_type(exercise_type, date, maturity):
    if exercise_type.upper() == 'AMERICAN':
        return ql.AmericanExercise(to_ql_date(date), to_ql_date(maturity))
    elif exercise_type.upper() == 'EUROPEAN':
        return ql.EuropeanExercise(to_ql_date(maturity))
    else:
        raise ValueError('Exercise type not supported')


class BaseEquityOption(Instrument):

    def __init__(self, timeseries, ql_process):
        super().__init__(timeseries)
        self.opt_type = self.ts_attributes[OPTION_TYPE]
        self.strike = self.ts_attributes[STRIKE_PRICE]
        self.contract_size = self.ts_attributes[OPTION_CONTRACT_SIZE]
        self.option_maturity = to_ql_date(to_datetime(self.ts_attributes[MATURITY_DATE]))
        self.payoff = ql.PlainVanillaPayoff(to_ql_option_type(self.opt_type), self.strike)
        self.calendar = to_ql_calendar(self.ts_attributes[CALENDAR])
        self.day_counter = to_ql_day_counter(self.ts_attributes[DAY_COUNTER])
        self.exercise_type = self.ts_attributes[EXERCISE_TYPE]
        self.underlying_instrument = self.ts_attributes[UNDERLYING_INSTRUMENT]
        self.ql_process = ql_process
        self.option = None

    def is_expired(self, date, *args, **kwargs):

        ql_date = to_ql_date(date)
        if ql_date >= self.option_maturity:
            return True
        return False

    def maturity(self, date, *args, **kwargs):

        return self.option_maturity

    @conditional_vectorize('date', 'quote')
    def value(self, date, quote=None, exercise_ovrd=None, *args, **kwargs):

        dt_date = to_datetime(date)
        size = float(self.contract_size)
        if quote is not None:
            return float(quote)*size
        else:
            return self.price(date=dt_date, exercise_ovrd=exercise_ovrd)*size

    @conditional_vectorize('date', 'quote')
    def performance(self, date=None, quote=None, start_date=None, start_quote=None, *args, **kwargs):

        first_available_date = self.ivol_mid.ts_values.first_valid_index()
        if start_date is None:
            start_date = first_available_date
        if start_date < first_available_date:
            start_date = first_available_date
        if date < start_date:
            return np.nan
        start_value = self.value(date=start_date, quote=quote, *args, **kwargs)
        value = self.value(date=date, quote=quote, *args, **kwargs)

        return (value / start_value) - 1

    @conditional_vectorize('date')
    def intrinsic(self, date):

        dt_date = to_datetime(date)
        strike = self.strike
        spot = self.ql_process.spot_price[dt_date].value()
        intrinsic = 0

        if self.opt_type == 'CALL':
            intrinsic = spot - strike
        if self.opt_type == 'PUT':
            intrinsic = strike - spot

        if intrinsic < 0:
            return 0
        else:
            return intrinsic

    def ql_option(self, date, exercise_ovrd=None):

        dt_date = to_datetime(date)
        if exercise_ovrd is not None:
            self.exercise_type = exercise_ovrd.upper()

        if self.exercise_type.upper() == 'AMERICAN':
            exercise = ql.AmericanExercise(to_ql_date(dt_date), self.option_maturity)

        elif self.exercise_type.upper() == 'EUROPEAN':
            exercise = ql.EuropeanExercise(self.option_maturity)
        else:
            raise ValueError('Type not supported')

        return ql.VanillaOption(self.payoff, exercise)

    @conditional_vectorize('date', 'mid_price')
    def implied_vol_process(self, date, mid_price, exercise_ovrd=None):

        dt_date = to_datetime(date)
        if self.option is None:
            self.option = self.ql_option(date=date, exercise_ovrd=exercise_ovrd)

        mid_price = mid_price
        ivol_last = 20
        self.ql_process = self.ql_process.update_missing_vol(date=dt_date, vol_value=ivol_last,
                                                             ts_name=self.ts_name)
        bsm_process = self.ql_process.process
        bsm_process_at_date = bsm_process[self.ts_name][dt_date]
        self.option.setPricingEngine(ql.BinomialVanillaEngine(bsm_process_at_date, "LR", 800))
        implied_vol = self.option.impliedVolatility(targetValue=mid_price, process=bsm_process_at_date)
        bsm_process = self.ql_process.update_only_vol(date=dt_date, vol_value=implied_vol * 100,
                                                      ts_name=self.ts_name).process

        return bsm_process

    @conditional_vectorize('date')
    def option_engine(self, date, exercise_ovrd=None):

        dt_date = to_datetime(date)
        self.option = self.ql_option(date=dt_date, exercise_ovrd=exercise_ovrd)
        bsm_process = self.ql_process.process
        try:
            bsm_process_at_date = bsm_process[self.ts_name][dt_date]
            self.option.setPricingEngine(ql.BinomialVanillaEngine(bsm_process_at_date, "LR", 800))

        except KeyError:
            mid_price = self.px_mid.ts_values.loc[dt_date]
            bsm_process = self.implied_vol_process(date=dt_date, mid_price=mid_price, exercise_ovrd=exercise_ovrd)
            bsm_process_at_date = bsm_process[self.ts_name][dt_date]
            self.option.setPricingEngine(ql.BinomialVanillaEngine(bsm_process_at_date, "LR", 800))

        return self.option

    @conditional_vectorize('date')
    def price(self, date, exercise_ovrd=None):

        ql.Settings.instance().evaluationDate = to_ql_date(date)
        option = self.option_engine(date=date, exercise_ovrd=exercise_ovrd)
        return option.NPV()

    @conditional_vectorize('date')
    def delta(self, date, exercise_ovrd=None):

        ql.Settings.instance().evaluationDate = to_ql_date(date)
        option = self.option_engine(date=date, exercise_ovrd=exercise_ovrd)
        return option.delta()

    @conditional_vectorize('date')
    def gamma(self, date, exercise_ovrd=None):

        ql.Settings.instance().evaluationDate = to_ql_date(date)
        option = self.option_engine(date=date, exercise_ovrd=exercise_ovrd)
        return option.gamma()

    @conditional_vectorize('date')
    def vega(self, date, exercise_ovrd=None):

        ql.Settings.instance().evaluationDate = to_ql_date(date)
        option = self.option_engine(date=date, exercise_ovrd=exercise_ovrd)
        if isinstance(self.exercise, ql.AmericanExercise):
            return None
        else:
            return option.vega()

    @conditional_vectorize('date')
    def rho(self, date, exercise_ovrd=None):

        ql.Settings.instance().evaluationDate = to_ql_date(date)
        option = self.option_engine(date=date, exercise_ovrd=exercise_ovrd)
        if isinstance(self.exercise, ql.AmericanExercise):
            return None
        else:
            return option.rho()

    @conditional_vectorize('date', 'target')
    def implied_vol(self, date, target, exercise_ovrd=None):

        if self.option is None:
            self.option = self.ql_option(date=date, exercise_ovrd=exercise_ovrd)

        ql.Settings.instance().evaluationDate = to_ql_date(date)
        dt_date = to_datetime(date)
        self.ql_process = self.ql_process.update_missing_vol(date=dt_date,
                                                             vol_value=20,
                                                             ts_name=self.ts_name)
        bsm_process = self.ql_process.process
        implied_vol = self.option.impliedVolatility(targetValue=target, process=bsm_process[self.ts_name][dt_date])

        return implied_vol*100

    @conditional_vectorize('date')
    def optionality(self, date, exercise_ovrd=None):

        price = self.price(date=date, exercise_ovrd=exercise_ovrd)
        intrinsic = self.intrinsic(date=date)
        return price - intrinsic
