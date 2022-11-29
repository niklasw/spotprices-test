#!/usr/bin/env python3

import os
import sys
import time
from datetime import datetime, timedelta
from dateutil import tz
from entsoe import EntsoeRawClient, parsers
from pathlib import Path
import pandas as pd
from dataclasses import dataclass
from matplotlib import pyplot as plt

API_KEY = os.getenv('ENTSOE_API_KEY')
TIME_ZONE = 'Europe/Stockholm'
TZ = tz.gettz(TIME_ZONE)


def day_start(time: datetime):
    return datetime(time.year, time.month, time.day, 0, 0, 0, 0, TZ)


@dataclass
class TimeSlot:
    start: datetime = None
    now: datetime = None
    end: datetime = None

    def inside(self, time: datetime = None):
        if not time:
            time = datetime.now(TZ)
        return self.start < time < self.end

    def __repr__(self):
        fmt = '%y%m%d-%H:%M:%S'

        def strf(t):
            return datetime.strftime(t, fmt)
        return f'{strf(self.start)} {strf(self.now)} {strf(self.end)}'


class TimeSlots:
    required_hours = 6

    def __init__(self, start_times: list = []):
        self.start_times: list = start_times
        self.slots: list = []
        self.find_slots()

    def append(self, start_times):
        self.start_times = start_times
        self.find_slots()

    def find_slots(self, dt=timedelta(hours=1)):
        now = datetime.now(TZ)
        times = self.start_times
        if len(times) > 1:
            slots = [TimeSlot(start=times[0], now=now)]
            for i in range(len(times)-1):
                if times[i] + dt >= times[i+1]:
                    slots[-1].end = times[i+1]+dt
                else:
                    slots[-1].end = times[i] + dt
                    slots.append(TimeSlot(start=times[i+1],
                                          now=now,
                                          end=times[i+1]+dt))
            self.slots += slots

    def inside(self, time: datetime = None):
        if time is None:
            time = datetime.now(TZ)
        return any((ts.inside(time) for ts in self.slots))

    def plottable(self, series):
        """Only for plotting"""
        t = series.index[0]
        t1 = series.index[-1] + timedelta(seconds=3600)
        values = []
        times = []
        dt = timedelta(seconds=36)
        while t < t1:
            t += dt
            times.append(t)
            values.append(1 if self.inside(t) else 0)
        return pd.Series(data=values, index=times)


class PriceList:
    cache_timeout_s = 6 * 3600

    def __init__(self, cache_file, service):
        self.cache: Path = Path(cache_file)
        self.service = service
        self.query_result = None
        self.prices: pd.TimeSeries = None

    def cache_age(self):
        if self.cache.exists():
            st_mtime = self.cache.stat().st_mtime
        else:
            st_mtime = 0
        return datetime.now(TZ) - datetime.fromtimestamp(st_mtime, TZ)

    def cache_write(self):
        if self.prices is not None:
            self.prices.to_json(self.cache, typ='series')

    def cache_read(self):
        p = pd.read_json(self.cache, typ='series').tz_localize('UTC')
        self.prices = p.tz_convert(TIME_ZONE)

    def get_prices(self):
        use_cache = self.cache_age().total_seconds() < self.cache_timeout_s
        if use_cache:
            print('READING')
            self.cache_read()
        else:
            print('FETCHING')
            self.prices = self.service.get_prices()
            self.cache_write()

    def get_daily_prices(self):
        self.get_prices()
        groups = self.prices.groupby(self.prices.index.date)
        # groupby returns a list of tuples (date, series), so filter out
        # the actual series.
        return [g[1] for g in groups]

    def cheapest_hours(self, prices: pd.Series, n_required_hours: int):
        cheapest = prices.sort_values()[0:n_required_hours]
        start_times = []
        for start_time in cheapest.index.sort_values():
            start_time = start_time.replace(tzinfo=TZ)
            start_times.append(start_time)
        return start_times

    def find_slots(self, slots: TimeSlots = None):
        h = TimeSlots.required_hours
        if slots is None:
            slots = TimeSlots()
        for day in self.get_daily_prices():
            slots.append(self.cheapest_hours(day, h))
        return slots


class Entsoe:
    def __init__(self):
        self.meter = '60T'

    def fetch(self):
        client = EntsoeRawClient(api_key=API_KEY)
        start = pd.Timestamp(datetime.now(), tz=TIME_ZONE)
        end = pd.Timestamp(datetime.now() + timedelta(days=1),
                           tz=TIME_ZONE)
        country_code = 'SE_3'
        query = client.query_day_ahead_prices(country_code, start, end)
        return query

    def get_prices(self):
        """The price list seems to be given in Greenwich time zone,
           so must convert index to time zone."""
        query_result = self.fetch()
        price_series = parsers.parse_prices(query_result)[self.meter]
        price_series.index = price_series.index.tz_convert(TIME_ZONE)
        return price_series


def test_run(slots):
    while True:
        print(f'{slots.inside()} :: {datetime.now(TZ)}')
        time.sleep(600)


def plot(prices, slots):
    _, (ax1, ax2) = plt.subplots(2, 1, sharex=True)
    x = prices.index
    slots.plot(ax=ax1, kind='line', color='red')
    prices.plot(ax=ax2, kind='line', color='green', drawstyle='steps-post')
    ax1.set_xlim(x[0], x[-1]+timedelta(hours=1))
    ax1.set_title('on/off signal, 6 hours daily demand')
    ax2.set_xlim(x[0], x[-1]+timedelta(hours=1))
    ax2.set_title('spot price')
    ax1.grid('on')
    ax2.grid('on')
    plt.show()


if __name__ == '__main__':
    TimeSlots.required_hours = int(sys.argv[1])

    price_list = PriceList('prices.json', Entsoe())
    slots = price_list.find_slots()

    if slots.inside():
        print(' -yes')
    else:
        print(' -no')

    for slot in slots.slots:
        print(slot)
    plot(price_list.prices, slots.plottable(price_list.prices))
