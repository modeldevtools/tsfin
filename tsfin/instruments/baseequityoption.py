# Copyright (C) 2016-2018 Lanx Capital Investimentos LTDA.
#
# This file is part of Time Series Finance (tsfin).
#
# Time Series Finance (tsfin) is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# Time Series Finance (tsfin) is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Time Series Finance (tsfin). If not, see <https://www.gnu.org/licenses/>.
"""
A class for modelling Equity Options
"""
import QuantLib as ql
import numpy as np
from tsfin.constants import CALENDAR, MATURITY_DATE, \
    DAY_COUNTER, EXERCISE_TYPE, OPTION_TYPE, STRIKE_PRICE, UNDERLYING_INSTRUMENT, OPTION_CONTRACT_SIZE
from tsfin.base import Instrument, to_ql_option_type, to_ql_date, conditional_vectorize, to_ql_calendar, \
    to_ql_day_counter, to_datetime, to_list


def option_exercise_type(exercise_type, date, maturity):
    if exercise_type.upper() == 'AMERICAN':
        return ql.AmericanExercise(date, maturity)
    elif exercise_type.upper() == 'EUROPEAN':
        return ql.EuropeanExercise(maturity)
    else:
        raise ValueError('Exercise type not supported')


def ql_option_type(*args):

    return ql.VanillaOption(*args)


def ql_option_payoff(*args):

    return ql.PlainVanillaPayoff(*args)


def ql_option_engine(process):

    model = str("LR")
    time_steps = 801
    return ql.BinomialVanillaEngine(process, model, time_steps)


class BaseEquityOption(Instrument):
    """ Model for Equity Options using the Black Scholes Merton model.

    :param timeseries: :py:class:`TimeSeries`
        The TimeSeries representing the option.

    Note
    ----
    See the :py:mod:`constants` for required attributes in `timeseries` and their possible values.
    """

    def __init__(self, timeseries):
        super().__init__(timeseries)
        self.opt_type = self.ts_attributes[OPTION_TYPE]
        self.strike = self.ts_attributes[STRIKE_PRICE]
        self.contract_size = self.ts_attributes[OPTION_CONTRACT_SIZE]
        self.option_maturity = to_ql_date(to_datetime(self.ts_attributes[MATURITY_DATE]))
        self.payoff = ql_option_payoff(to_ql_option_type(self.opt_type), self.strike)
        self.calendar = to_ql_calendar(self.ts_attributes[CALENDAR])
        self.day_counter = to_ql_day_counter(self.ts_attributes[DAY_COUNTER])
        self.exercise_type = self.ts_attributes[EXERCISE_TYPE]
        self.underlying_instrument = self.ts_attributes[UNDERLYING_INSTRUMENT]
        self.ql_process = None
        self.option = None
        self.implied_volatility = dict()

    def set_ql_process(self, ql_process):
        """
        :param ql_process: :py:class:'BlackScholesMerton'
            A class used to handle the Black Scholes Merton model from QuantLib.
        :return:
        """
        self.ql_process = ql_process

    def is_expired(self, date, *args, **kwargs):
        """
        :param date: date-like
            The date.
        :return bool
            True if the instrument is expired or matured, False otherwise.
        """
        ql_date = to_ql_date(date)
        if ql_date >= self.option_maturity:
            return True
        return False

    def maturity(self, date, *args, **kwargs):
        """
        :param date: date-like
            The date.
        :return QuantLib.Date, None
            Date representing the maturity or expiry of the instrument. Returns None if there is no maturity.
        """
        return self.option_maturity

    @conditional_vectorize('date', 'quote', 'volatility')
    def value(self, date, base_date, quote=None, volatility=None, dvd_tax_adjust=1, last_available=True,
              exercise_ovrd=None, *args, **kwargs):
        """Try to deduce dirty value for a unit of the time series (as a financial instrument).

        :param date: date-like
            The date.
        :param base_date: date-like
            When date is a future date base_date is the last date on the "present" used to estimate future values.
        :param quote: scalar, optional
            The quote.
        :param volatility: float, optional
            Volatility override value to calculate the option.
        :param dvd_tax_adjust: float, default=1
            The multiplier used to adjust for dividend tax. For example, US dividend taxes are 30% so you pass 0.7.
        :param last_available: bool, optional
            Whether to use last available data in case dates are missing in ``quotes``.
        :param exercise_ovrd: str, optional
            Used to force the option model to use a specific type of option. Only working for American and European
            option types.
        :return scalar, None
            The unit dirty value of the instrument.
        """
        ql_date = to_ql_date(date)
        ql_base_date = to_ql_date(base_date)
        size = float(self.contract_size)
        if quote is not None:
            return float(quote)*size
        else:
            return self.price(date=ql_date, base_date=ql_base_date, dvd_tax_adjust=dvd_tax_adjust,
                              last_available=last_available, exercise_ovrd=exercise_ovrd, volatility=volatility)*size

    @conditional_vectorize('date', 'quote')
    def performance(self, date=None, quote=None, start_date=None, start_quote=None, *args, **kwargs):
        """
        Parameters
        ----------
        :param start_date: datetime-like, optional
            The starting date of the period.
            Default: The first date in ``self.quotes``.
        :param date: datetime-like, optional, (c-vectorized)
            The ending date of the period.
            Default: see :py:func:`default_arguments`.
        :param start_quote: scalar, optional, (c-vectorized)
            The quote of the instrument in `start_date`.
            Default: the quote in `start_date`.
        :param quote: scalar, optional, (c-vectorized)
            The quote of the instrument in `date`.
            Default: see :py:func:`default_arguments`.
        :return scalar, None
            Performance of a unit of the option.
        """
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

    def notional(self):
        """
        :return: float
            The notional of the contract based on the option contract size and strike.
        """
        return float(self.contract_size)*float(self.strike)

    @conditional_vectorize('date')
    def intrinsic(self, date):
        """
        :param date: date-like
            The date
        :return: float
            The intrinsic value o the option at date.
        """
        ql_date = to_ql_date(date)
        strike = self.strike
        if ql_date > self.option_maturity:
            return 0
        else:
            underlying_instrument = self.ql_process.equity_instruments.get(self.underlying_instrument)
            spot = float(underlying_instrument.spot_price(date=date, last_available=True))
            intrinsic = 0

            if self.opt_type == 'CALL':
                intrinsic = spot - strike
            if self.opt_type == 'PUT':
                intrinsic = strike - spot

            if intrinsic < 0:
                return 0
            else:
                return intrinsic
    
    def ts_mid_price(self, date, last_available=True, fill_value=np.nan):

        date = to_datetime(to_list(date))
        return self.px_mid.get_values(index=date, last_available=last_available, fill_value=fill_value)

    def ts_implied_volatility(self, date, last_available=False, fill_value=np.nan):

        date = to_datetime(to_list(date))
        return self.ivol_mid.get_values(index=date, last_available=last_available, fill_value=fill_value)

    @conditional_vectorize('date')
    def ql_option(self, date, exercise_ovrd=None):

        """
        :param date: date-like
            The date
        :param exercise_ovrd: str, optional
            Used to force the option model to use a specific type of option. Only working for American and European
            option types.
        :return: QuantLib.VanillaOption
        """

        ql_date = to_ql_date(date)
        if exercise_ovrd is not None:
            self.exercise_type = exercise_ovrd.upper()

        exercise = option_exercise_type(self.exercise_type, date=ql_date, maturity=self.option_maturity)

        return ql_option_type(self.payoff, exercise)

    def option_engine(self, date, base_date, dvd_tax_adjust=1, last_available=True, exercise_ovrd=None, volatility=None,
                      underlying_price=None):

        """
        :param date: QuantLib.Date
            The date.
        :param base_date: date-like
            When date is a future date base_date is the last date on the "present" used to estimate future values.
        :param dvd_tax_adjust: float, default=1
            The multiplier used to adjust for dividend tax. For example, US dividend taxes are 30% so you pass 0.7.
        :param last_available: bool, optional
            Whether to use last available data in case dates are missing in ``quotes``.
        :param exercise_ovrd: str, optional
            Used to force the option model to use a specific type of option. Only working for American and European
            option types.
        :param volatility: float, optional
            Volatility override value to calculate the option.
        :param underlying_price: float, optional
            Underlying price override value to calculate the option.
        :return: QuantLib.VanillaOption
            This method returns the VanillaOption with a QuantLib engine. Used for calculating the option values
            and greeks.
        """
        self.option = self.ql_option(date=date, exercise_ovrd=exercise_ovrd)
        self.ql_process.update_process(date=date, base_date=base_date, calendar=self.calendar,
                                       day_counter=self.day_counter,
                                       underlying_name=self.underlying_instrument,
                                       vol_value=0.2,
                                       maturity=self.option_maturity,
                                       dvd_tax_adjust=dvd_tax_adjust,
                                       last_available=last_available,
                                       spot_price=underlying_price)
        self.option.setPricingEngine(ql_option_engine(self.ql_process.bsm_process))

        if date > base_date:
            date = base_date
        if volatility is not None:
            self.implied_volatility[date] = ql.SimpleQuote(volatility)
        try:
            self.ql_process.volatility_update(vol_value=self.implied_volatility[date], calendar=self.calendar,
                                              day_counter=self.day_counter)
        except KeyError:
            mid_price = float(self.ts_mid_price(date=date, last_available=True))
            try:
                implied_vol = self.option.impliedVolatility(targetValue=mid_price,
                                                            process=self.ql_process.bsm_process,
                                                            accuracy=1.0e-4, maxEvaluations=100)
            except RuntimeError:
                prior_date = self.calendar.advance(date, -1, ql.Days)
                mid_price = float(self.ts_mid_price(date=prior_date, last_available=True))
                implied_vol = self.option.impliedVolatility(targetValue=mid_price,
                                                            process=self.ql_process.bsm_process,
                                                            accuracy=1.0e-4, maxEvaluations=100)
            self.implied_volatility[date] = ql.SimpleQuote(implied_vol)
            self.ql_process.volatility_update(vol_value=self.implied_volatility[date], calendar=self.calendar,
                                              day_counter=self.day_counter)
        return self.option

    @conditional_vectorize('date', 'volatility', 'underlying_price')
    def price(self, date, base_date, dvd_tax_adjust=1, last_available=True, exercise_ovrd=None, volatility=None,
              underlying_price=None):
        """
        :param date: date-like
            The date.
        :param base_date: date-like
            When date is a future date base_date is the last date on the "present" used to estimate future values.
        :param dvd_tax_adjust: float, default=1
            The multiplier used to adjust for dividend tax. For example, US dividend taxes are 30% so you pass 0.7.
        :param last_available: bool, optional
            Whether to use last available data in case dates are missing in ``quotes``.
        :param exercise_ovrd: str, optional
            Used to force the option model to use a specific type of option. Only working for American and European
            option types.
        :param volatility: float, optional
            Volatility override value to calculate the option.
        :param underlying_price: float, optional
            Underlying price override value to calculate the option.
        :return: float
            The option price at date.
        """
        date = to_ql_date(date)
        base_date = to_ql_date(base_date)
        ql.Settings.instance().evaluationDate = date
        if date >= self.option_maturity:
            if self.option_maturity >= base_date:
                return self.intrinsic(date=self.option_maturity)
            else:
                return self.intrinsic(date=base_date)
        else:
            option = self.option_engine(date=date, base_date=base_date, dvd_tax_adjust=dvd_tax_adjust,
                                        last_available=last_available, exercise_ovrd=exercise_ovrd,
                                        volatility=volatility, underlying_price=underlying_price)
        return option.NPV()

    @conditional_vectorize('date', 'spot_price')
    def price_underlying(self, date, spot_price, base_date, dvd_tax_adjust=1, last_available=True, exercise_ovrd=None,
                         volatility=None):
        """
        :param date: date-like
            The date.
        :param spot_price: float
            The underlying spot prices used for evaluation.
        :param base_date: date-like
            When date is a future date base_date is the last date on the "present" used to estimate future values.

        :param dvd_tax_adjust: float, default=1
            The multiplier used to adjust for dividend tax. For example, US dividend taxes are 30% so you pass 0.7.
        :param last_available: bool, optional
            Whether to use last available data in case dates are missing in ``quotes``.
        :param exercise_ovrd: str, optional
            Used to force the option model to use a specific type of option. Only working for American and European
            option types.
        :param volatility: float, optional
            Volatility override value to calculate the option.
        :return: float
            The option price based on the date and underlying spot price.
        """
        date = to_ql_date(date)
        base_date = to_ql_date(base_date)
        ql.Settings.instance().evaluationDate = date
        option = self.option_engine(date=date, base_date=base_date, dvd_tax_adjust=dvd_tax_adjust,
                                    last_available=last_available, exercise_ovrd=exercise_ovrd, volatility=volatility)

        self.ql_process.spot_price_update(date=date, underlying_name=self.underlying_instrument, spot_price=spot_price)
        return option.NPV()

    @conditional_vectorize('date', 'volatility', 'underlying_price')
    def delta(self, date, base_date, dvd_tax_adjust=1, last_available=True, exercise_ovrd=None, volatility=None,
              underlying_price=None):
        """
        :param date: date-like
            The date.
        :param base_date: date-like
            When date is a future date base_date is the last date on the "present" used to estimate future values.
        :param dvd_tax_adjust: float, default=1
            The multiplier used to adjust for dividend tax. For example, US dividend taxes are 30% so you pass 0.7.
        :param last_available: bool, optional
            Whether to use last available data in case dates are missing in ``quotes``.
        :param exercise_ovrd: str, optional
            Used to force the option model to use a specific type of option. Only working for American and European
            option types.
        :param volatility: float, optional
            Volatility override value to calculate the option.
        :param underlying_price: float, optional
            Underlying price override value to calculate the option.
        :return: float
            The option delta at date.
        """
        date = to_ql_date(date)
        base_date = to_ql_date(base_date)
        ql.Settings.instance().evaluationDate = date
        if date >= self.option_maturity:
            if self.intrinsic(date=self.option_maturity) > 0:
                return 1
            else:
                return 0
        else:
            option = self.option_engine(date=date, base_date=base_date, dvd_tax_adjust=dvd_tax_adjust,
                                        last_available=last_available, exercise_ovrd=exercise_ovrd,
                                        volatility=volatility, underlying_price=underlying_price)
            return option.delta()

    @conditional_vectorize('date', 'spot_price')
    def delta_underlying(self, date, spot_price, base_date, dvd_tax_adjust=1, last_available=True, exercise_ovrd=None,
                         volatility=None):
        """
        :param date: date-like
            The date.
        :param spot_price: float
            The underlying spot prices used for evaluation.
        :param base_date: date-like
            When date is a future date base_date is the last date on the "present" used to estimate future values.
        :param dvd_tax_adjust: float, default=1
            The multiplier used to adjust for dividend tax. For example, US dividend taxes are 30% so you pass 0.7.
        :param last_available: bool, optional
            Whether to use last available data in case dates are missing in ``quotes``.
        :param exercise_ovrd: str, optional
            Used to force the option model to use a specific type of option. Only working for American and European
            option types.
        :param volatility: float, optional
            Volatility override value to calculate the option.
        :return: float
            The option delta based on the date and underlying spot price.
        """
        date = to_ql_date(date)
        base_date = to_ql_date(base_date)
        ql.Settings.instance().evaluationDate = date
        option = self.option_engine(date=date, base_date=base_date, dvd_tax_adjust=dvd_tax_adjust,
                                    last_available=last_available, exercise_ovrd=exercise_ovrd, volatility=volatility)
        self.ql_process.spot_price_update(date=date, underlying_name=self.underlying_instrument, spot_price=spot_price)
        return option.delta()

    @conditional_vectorize('date', 'volatility', 'underlying_price')
    def gamma(self, date, base_date, dvd_tax_adjust=1, last_available=True, exercise_ovrd=None, volatility=None,
              underlying_price=None):
        """
        :param date: date-like
            The date.
        :param base_date: date-like
            When date is a future date base_date is the last date on the "present" used to estimate future values.
        :param dvd_tax_adjust: float, default=1
            The multiplier used to adjust for dividend tax. For example, US dividend taxes are 30% so you pass 0.7.
        :param last_available: bool, optional
            Whether to use last available data in case dates are missing in ``quotes``.
        :param exercise_ovrd: str, optional
            Used to force the option model to use a specific type of option. Only working for American and European
            option types.
        :param volatility: float, optional
            Volatility override value to calculate the option.
        :param underlying_price: float, optional
            Underlying price override value to calculate the option.
        :return: float
            The option gamma at date.
        """
        date = to_ql_date(date)
        base_date = to_ql_date(base_date)
        ql.Settings.instance().evaluationDate = date
        if date >= self.option_maturity:
            return 0
        else:
            option = self.option_engine(date=date, base_date=base_date, dvd_tax_adjust=dvd_tax_adjust,
                                        last_available=last_available, exercise_ovrd=exercise_ovrd,
                                        volatility=volatility, underlying_price=underlying_price)
            return option.gamma()

    @conditional_vectorize('date', 'volatility', 'underlying_price')
    def theta(self, date,  base_date, dvd_tax_adjust=1, last_available=True, exercise_ovrd=None, volatility=None,
              underlying_price=None):
        """
        :param date: date-like
            The date.
        :param base_date: date-like
            When date is a future date base_date is the last date on the "present" used to estimate future values.
        :param dvd_tax_adjust: float, default=1
            The multiplier used to adjust for dividend tax. For example, US dividend taxes are 30% so you pass 0.7.
        :param last_available: bool, optional
            Whether to use last available data in case dates are missing in ``quotes``.
        :param exercise_ovrd: str, optional
            Used to force the option model to use a specific type of option. Only working for American and European
            option types.
        :param volatility: float, optional
            Volatility override value to calculate the option.
        :param underlying_price: float, optional
            Underlying price override value to calculate the option.
        :return: float
            The option theta at date.
        """
        date = to_ql_date(date)
        base_date = to_ql_date(base_date)
        ql.Settings.instance().evaluationDate = date
        if date >= self.option_maturity:
            return 0
        else:
            option = self.option_engine(date=date, base_date=base_date, dvd_tax_adjust=dvd_tax_adjust,
                                        last_available=last_available, exercise_ovrd=exercise_ovrd,
                                        volatility=volatility, underlying_price=underlying_price)
            return option.theta()

    @conditional_vectorize('date', 'volatility', 'underlying_price')
    def vega(self, date, base_date, dvd_tax_adjust=1, last_available=True, exercise_ovrd=None, volatility=None,
             underlying_price=None):
        """
        :param date: date-like
            The date.
        :param base_date: date-like
            When date is a future date base_date is the last date on the "present" used to estimate future values.
        :param dvd_tax_adjust: float, default=1
            The multiplier used to adjust for dividend tax. For example, US dividend taxes are 30% so you pass 0.7.
        :param last_available: bool, optional
            Whether to use last available data in case dates are missing in ``quotes``.
        :param exercise_ovrd: str, optional
            Used to force the option model to use a specific type of option. Only working for American and European
            option types.
        :param volatility: float, optional
            Volatility override value to calculate the option.
        :param underlying_price: float, optional
            Underlying price override value to calculate the option.
        :return: float
            The option vega at date.
        """
        date = to_ql_date(date)
        base_date = to_ql_date(base_date)
        ql.Settings.instance().evaluationDate = date
        if date >= self.option_maturity:
            return 0
        else:
            option = self.option_engine(date=date, base_date=base_date, dvd_tax_adjust=dvd_tax_adjust,
                                        last_available=last_available, exercise_ovrd=exercise_ovrd,
                                        volatility=volatility, underlying_price=underlying_price)
            if self.exercise_type == 'AMERICAN':
                return None
            else:
                try:
                    return option.vega()
                except:
                    return 0

    @conditional_vectorize('date', 'volatility', 'underlying_price')
    def rho(self, date, base_date, dvd_tax_adjust=1, last_available=True, exercise_ovrd=None, volatility=None,
            underlying_price=None):
        """
        :param date: date-like
            The date.
        :param base_date: date-like
            When date is a future date base_date is the last date on the "present" used to estimate future values.
        :param dvd_tax_adjust: float, default=1
            The multiplier used to adjust for dividend tax. For example, US dividend taxes are 30% so you pass 0.7.
        :param last_available: bool, optional
            Whether to use last available data in case dates are missing in ``quotes``.
        :param exercise_ovrd: str, optional
            Used to force the option model to use a specific type of option. Only working for American and European
            option types.
        :param volatility: float, optional
            Volatility override value to calculate the option.
        :param underlying_price: float, optional
            Underlying price override value to calculate the option.
        :return: float
            The option rho at date.
        """
        date = to_ql_date(date)
        base_date = to_ql_date(base_date)
        ql.Settings.instance().evaluationDate = date
        if date >= self.option_maturity:
            return 0
        else:
            option = self.option_engine(date=date, base_date=base_date, dvd_tax_adjust=dvd_tax_adjust,
                                        last_available=last_available, exercise_ovrd=exercise_ovrd,
                                        volatility=volatility, underlying_price=underlying_price)
            if self.exercise_type == 'AMERICAN':
                return None
            else:
                try:
                    return option.rho()
                except:
                    return 0

    @conditional_vectorize('date', 'target', 'spot_price')
    def implied_vol(self, date, target, spot_price=None, dvd_tax_adjust=1, last_available=True, exercise_ovrd=None,
                    volatility=0.2):
        """
        :param date: date-like
            The date.
        :param target: float
           The option price used to calculate the implied volatility.
        :param spot_price: float, optional
            The underlying spot prices used for evaluation.
        :param dvd_tax_adjust: float, default=1
            The multiplier used to adjust for dividend tax. For example, US dividend taxes are 30% so you pass 0.7.
        :param last_available: bool, optional
            Whether to use last available data in case dates are missing in ``quotes``.
        :param exercise_ovrd: str, optional
            Used to force the option model to use a specific type of option. Only working for American and European
            option types.
        :param volatility: float, optional
            Volatility override value to calculate the option.
        :return: float
            The option volatility based on the option price and date.
        """
        date = to_ql_date(date)
        ql.Settings.instance().evaluationDate = date
        if self.option is None:
            self.option = self.option_engine(date=date, base_date=date, dvd_tax_adjust=dvd_tax_adjust,
                                             last_available=last_available, exercise_ovrd=exercise_ovrd,
                                             volatility=volatility)
        if spot_price is not None:
            self.ql_process.spot_price_update(date=date, underlying_name=self.underlying_instrument,
                                              spot_price=spot_price)

        return self.option.impliedVolatility(target, self.ql_process.bsm_process)

    @conditional_vectorize('date', 'volatility', 'underlying_price')
    def optionality(self, date, base_date, dvd_tax_adjust=1, last_available=True, exercise_ovrd=None, volatility=None,
                    underlying_price=None):
        """
        :param date: date-like
            The date.
        :param base_date: date-like
            When date is a future date base_date is the last date on the "present" used to estimate future values.
        :param dvd_tax_adjust: float, default=1
            The multiplier used to adjust for dividend tax. For example, US dividend taxes are 30% so you pass 0.7.
        :param last_available: bool, optional
            Whether to use last available data in case dates are missing in ``quotes``.
        :param exercise_ovrd: str, optional
            Used to force the option model to use a specific type of option. Only working for American and European
            option types.
        :param volatility: float, optional
            Volatility override value to calculate the option.
        :param underlying_price: float, optional
            Underlying price override value to calculate the option.
        :return: float
            The option optionality at date.
        """
        date = to_ql_date(date)
        base_date = to_ql_date(base_date)
        if date >= self.option_maturity:
            return 0
        else:
            ql.Settings.instance().evaluationDate = date
            option = self.option_engine(date=date, base_date=base_date, dvd_tax_adjust=dvd_tax_adjust,
                                        last_available=last_available, exercise_ovrd=exercise_ovrd,
                                        volatility=volatility, underlying_price=underlying_price)
            price = option.NPV()
            if date > base_date:
                intrinsic = self.intrinsic(date=base_date)
            else:
                intrinsic = self.intrinsic(date=date)
            return price - intrinsic

    @conditional_vectorize('date')
    def underlying_price(self, date, base_date, dvd_tax_adjust=1, last_available=True, exercise_ovrd=None,
                         volatility=None):
        """
        :param date: date-like
            The date.
        :param base_date: date-like
            When date is a future date base_date is the last date on the "present" used to estimate future values.
        :param dvd_tax_adjust: float, default=1
            The multiplier used to adjust for dividend tax. For example, US dividend taxes are 30% so you pass 0.7.
        :param last_available: bool, optional
            Whether to use last available data in case dates are missing in ``quotes``.
        :param exercise_ovrd: str, optional
            Used to force the option model to use a specific type of option. Only working for American and European
            option types.
        :param volatility: float, optional
            Volatility override value to calculate the option.
        :return: float
            The option underlying spot price.
        """
        date = to_ql_date(date)
        base_date = to_ql_date(base_date)
        if date >= self.option_maturity:
            return 0
        else:
            ql.Settings.instance().evaluationDate = date
            self.option_engine(date=date, base_date=base_date, dvd_tax_adjust=dvd_tax_adjust,
                               last_available=last_available, exercise_ovrd=exercise_ovrd, volatility=volatility)
            return self.ql_process.spot_price_handle.value()

    @conditional_vectorize('date', 'volatility', 'underlying_price')
    def delta_value(self, date, base_date, dvd_tax_adjust=1, last_available=True, exercise_ovrd=None, volatility=None):
        """
        :param date: date-like
            The date.
        :param base_date: date-like
            When date is a future date base_date is the last date on the "present" used to estimate future values.
        :param dvd_tax_adjust: float, default=1
            The multiplier used to adjust for dividend tax. For example, US dividend taxes are 30% so you pass 0.7.
        :param last_available: bool, optional
            Whether to use last available data in case dates are missing in ``quotes``.
        :param exercise_ovrd: str, optional
            Used to force the option model to use a specific type of option. Only working for American and European
            option types.
        :param volatility: float, optional
            Volatility override value to calculate the option.
        :return: float
            The option delta notional value.
        """
        delta = self.delta(date=date, base_date=base_date, dvd_tax_adjust=dvd_tax_adjust, last_available=last_available,
                           exercise_ovrd=exercise_ovrd, volatility=volatility)
        spot = self.ql_process.spot_price_handle.value()
        size = float(self.contract_size)
        return delta*spot*size
