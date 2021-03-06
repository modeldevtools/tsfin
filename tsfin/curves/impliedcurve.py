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
ImpliedYieldCurveTimeSeries, a class to handle a time series of implied yield curves.
"""

import QuantLib as ql
from tsfin.base import to_ql_date, conditional_vectorize


class ImpliedYieldCurveTimeSeries:

    def __init__(self, yield_curve_time_series, base_date):
        self.yield_curve_time_series = yield_curve_time_series
        self.day_counter = self.yield_curve_time_series.day_counter
        self.calendar = self.yield_curve_time_series.calendar
        self.base_date = to_ql_date(base_date)

    def yield_curve(self, date):

        """ Get the QuantLib yield curve object at a given date.

        Parameters
        ----------
        date: QuantLib.Date
            The date of the yield curve.

        Returns
        -------
        QuantLib.ImpliedTermStructure
            The implied yield curve at `date`.
        """

        date = to_ql_date(date)
        return ql.ImpliedTermStructure(self.yield_curve_time_series.yield_curve_handle(self.base_date), date)

    def yield_curve_handle(self, date):
        """ Handle for a yield curve at a given date.

        Parameters
        ----------
        date: QuantLib.Date
            Date of the yield curve.

        Returns
        -------
        QuantLib.YieldTermStructureHandle
            A handle to the yield term structure object.
        """
        return ql.YieldTermStructureHandle(self.yield_curve(date))

    @conditional_vectorize('date', 'to_date')
    def zero_rate_to_date(self, date, to_date, compounding, frequency, extrapolate=True, day_counter=None):
        """
        Parameters
        ----------
        date: QuantLib.Date, (c-vectorized)
            Date of the yield curve.
        to_date: QuantLib.Date, (c-vectorized)
            Maturity of the rate.
        compounding: QuantLib.Compounding
            Compounding convention for the rate.
        frequency: QuantLib.Frequency
            Frequency convention for the rate.
        extrapolate: bool, optional
            Whether to enable extrapolation.
        day_counter: QuantLib.DayCounter, optional
            The day counter for the calculation.

        Returns
        -------
        scalar
            Zero rate for `to_date`, implied by the yield curve at `date`.
        """
        to_date = to_ql_date(to_date)
        day_counter = day_counter if day_counter is not None else self.day_counter
        return self.yield_curve(date).zeroRate(to_date, day_counter, compounding, frequency, extrapolate).rate()

    @conditional_vectorize('date', 'to_date1', 'to_date2')
    def forward_rate_date_to_date(self, date, to_date1, to_date2, compounding, frequency, extrapolate=True,
                                  day_counter=None):
        """
        Parameters
        ----------
        date: QuantLib.Date, (c-vectorized)
            Date of the yield curve.
        to_date1: QuantLib.Date, (c-vectorized)
            First maturity for the fra.
        to_date2: QuantLib.Date, (c-vectorized)
            Second maturity for the fra.
        compounding: QuantLib.Compounding
            Compounding convention for the rate.
        frequency: QuantLib.Frequency
            Frequency convention for the rate.
        extrapolate: bool, optional
            Whether to enable extrapolation.
        day_counter: QuantLib.DayCounter, optional
            The day counter for the calculation.

        Returns
        -------
        scalar
            Forward rate between `to_date1` and `to_date2`, implied by the yield curve at `date`.
        """
        to_date1 = to_ql_date(to_date1)
        to_date2 = to_ql_date(to_date2)
        day_counter = day_counter if day_counter is not None else self.day_counter
        return self.yield_curve(date).forwardRate(to_date1, to_date2, day_counter, compounding, frequency,
                                                  extrapolate).rate()
