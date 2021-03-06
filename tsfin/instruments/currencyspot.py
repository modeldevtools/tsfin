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
Currency class, to represent Currency Spot.
"""
import QuantLib as ql
import numpy as np
from pprint import pformat
from tsfin.constants import CALENDAR, CURRENCY, BASE_CURRENCY, COUNTRY, BASE_CALENDAR, QUOTES
from tsfin.base import Instrument, to_ql_calendar, conditional_vectorize, to_upper_list


class Currency(Instrument):
    """ Model Currency Spot.

    :param timeseries: :py:class:`TimeSeries`
        The TimeSeries representing the Currency.
    Note
    ----
    See the :py:mod:`constants` for required attributes in `timeseries` and their possible values.
    """

    def __init__(self, timeseries):
        super().__init__(timeseries=timeseries)
        self.currency = self.ts_attributes[CURRENCY]
        self.base_currency = self.ts_attributes[BASE_CURRENCY]
        self.calendar = to_ql_calendar(self.ts_attributes[CALENDAR])
        self.base_calendar = to_ql_calendar(self.ts_attributes[BASE_CALENDAR])
        self.country = self.ts_attributes[COUNTRY]

    @conditional_vectorize('date')
    def value(self, date, currency=None, last_available=False, *args, **kwargs):

        currency = self.currency if currency is None else to_upper_list(currency)
        if len(currency) != 3:
            return np.nan
        if self.currency == self.base_currency:
            return 1
        if currency == self.currency:
            return self.quotes.get_values(index=date, last_available=last_available)
        elif currency == self.base_currency:
            return 1/self.quotes.get_values(index=date, last_available=last_available)
        else:
            return np.nan

    @conditional_vectorize('date')
    def risk_value(self, date, currency=None, last_available=False, *args, **kwargs):

        return self.value(date=date, currency=currency, last_available=last_available, *args, **kwargs)

    def security(self, date, currency=None, last_available=False, *args, **kwargs):

        currency = self.currency if currency is None else to_upper_list(currency)
        if currency == self.base_currency:
            price = 1/self.quotes.get_values(index=date, last_available=last_available)
        else:
            price = self.quotes.get_values(index=date, last_available=last_available)

        return ql.Stock(ql.QuoteHandle(ql.SimpleQuote(price)))


class Cash(Currency):
    """ Model for Cash Values.

    :param timeseries: :py:class:`TimeSeries`
        The TimeSeries representing the Currency.
    Note
    ----
    See the :py:mod:`constants` for required attributes in `timeseries` and their possible values.
    """

    def __init__(self, timeseries, currency_timeseries):
        super().__init__(timeseries=timeseries)
        self.currency_timeseries = Instrument(currency_timeseries)
        self.currency = self.ts_attributes[CURRENCY]
        self.base_currency = self.ts_attributes[BASE_CURRENCY]
        self.calendar = to_ql_calendar(self.ts_attributes[CALENDAR])
        self.base_calendar = to_ql_calendar(self.ts_attributes[BASE_CALENDAR])
        self.country = self.ts_attributes[COUNTRY]

    def __str__(self):
        return '='*20 + '\n' \
               'class name: ' + self.__class__.__name__ + '\n' \
               + self.ts_name + '\n' \
               + '-'*20 + '\n' + \
               'ts_attributes:' + 2*'\n' \
               + str(pformat(self.ts_attributes)) + 2*'\n' \
               + '-'*20 + '\n' \
               + 'ts_values:' + 2*'\n' \
               + str(self.ts_values) + 2*'\n' \
               + '-' * 20 + '\n' \
               + '=' * 20 + '\n'

    @conditional_vectorize('date')
    def value(self, date, currency=None, last_available=False, *args, **kwargs):

        currency = self.currency if currency is None else to_upper_list(currency)
        currency_quotes = self.currency_timeseries.quotes
        if len(currency) != 3:
            return np.nan
        if self.currency == self.base_currency:
            return 1
        if currency == self.currency:
            return currency_quotes.get_values(index=date, last_available=last_available)
        elif currency == self.base_currency:
            return 1/currency_quotes.get_values(index=date, last_available=last_available)
        else:
            return np.nan

    @conditional_vectorize('date')
    def risk_value(self, date, currency=None, last_available=False, *args, **kwargs):

        return self.value(date=date, currency=currency, last_available=last_available, *args, **kwargs)

    def security(self, date, currency=None, last_available=False, *args, **kwargs):

        currency = self.currency if currency is None else to_upper_list(currency)
        currency_quotes = self.currency_timeseries.quotes
        if currency == self.base_currency:
            price = 1/currency_quotes.get_values(index=date, last_available=last_available)
        elif self.currency == self.base_currency:
            price = 1
        else:
            price = currency_quotes.get_values(index=date, last_available=last_available)

        return ql.Stock(ql.QuoteHandle(ql.SimpleQuote(price)))
