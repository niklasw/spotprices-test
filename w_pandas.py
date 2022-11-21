#!/usr/bin/env python3

import os
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

    def as_pd_series(self):
        """Only for plotting"""
        times = []
        values = []
        for slot in self.slots:
            times += [slot.start, slot.start, slot.end, slot.end]
            values += [0, 1, 1, 0]
        return pd.Series(data=values, index=times)

    def plottable(self, series):
        values = []
        for t in series.index:
            values.append(1 if self.inside(t+timedelta(hours=0.5)) else 0)
        return pd.Series(data=values, index=series.index)

    def plottable2(self, series):
        t = series.index[0]
        t1 = series.index[-1] + timedelta(seconds=3600)
        values = []
        times = []
        dt = timedelta(seconds=60)
        while t < t1:
            t += dt
            times.append(t)
            values.append(1 if self.inside(t) else 0)
        return pd.Series(data=values, index=times)


class ENTSOE:
    def __init__(self, cache_file):
        self.cache: Path = Path(cache_file)
        self.meter = '60T'
        self.query = None

    def cache_age(self):
        if self.cache.exists():
            st_mtime = self.cache.stat().st_mtime
        else:
            st_mtime = 0
        return datetime.now(TZ) - datetime.fromtimestamp(st_mtime, TZ)

    def fetch(self, use_cache):
        if use_cache and self.cache.exists():
            print('READING')
            with self.cache.open('r') as f:
                self.query = f.read()
        else:
            print('FETCHING')
            client = EntsoeRawClient(api_key=API_KEY)
            start = pd.Timestamp(datetime.now(), tz=TIME_ZONE)
            end = pd.Timestamp(datetime.now() + timedelta(days=1),
                               tz=TIME_ZONE)
            country_code = 'SE_3'
            query = client.query_day_ahead_prices(country_code, start, end)
            with self.cache.open('w') as f:
                f.write(query)
            self.query = query

    def get_prices(self):
        use_cache = self.cache_age().total_seconds() < 6*3600
        self.fetch(use_cache)
        return parsers.parse_prices(self.query)[self.meter]

    def get_daily_prices(self):
        prices = self.get_prices()
        # groupby returns a list of tuples (date, series)
        return prices.groupby(prices.index.date)


def cheapest_hours(prices, n_required_hours: int):
    cheapest = prices.sort_values()[0:n_required_hours]
    for start_time in cheapest.index.sort_values():
        start_time = start_time.replace(tzinfo=TZ)
        yield start_time  # .to_pydatetime()


def test_run(slots):
    while True:
        print(f'{slots.inside()} :: {datetime.now(TZ)}')
        time.sleep(600)


def plot(prices, slots):
    _, (ax1, ax2) = plt.subplots(2, 1, sharex=False)
    x = prices.index
    slots.plot(ax=ax1, kind='line', color='red')
    prices.plot(ax=ax2, kind='line', marker='o', color='green')
    ax1.set_xlim(x[0], x[-1])
    ax2.set_xlim(x[0], x[-1])
    ax1.grid('on')
    ax2.grid('on')
    plt.show()


if __name__ == '__main__':
    collector = ENTSOE('cache.xml')
    day_prices = collector.get_daily_prices()
    slots = TimeSlots()
    for day in day_prices:
        print(day[0])
        cheapest = list(cheapest_hours(day[1], 4))
        slots.append(cheapest)
        for item in cheapest:
            print('>>> ', item)

    for slot in slots.slots:
        print('+++', slot)

    print('is this a good time?')
    if slots.inside():
        print(' -yes')
    else:
        print(' -no')

    prices = pd.concat((a[1] for a in day_prices))
    plot(prices, slots.plottable2(prices))
    # plot(prices, slots.as_pd_series())
    # test_run(slots)
