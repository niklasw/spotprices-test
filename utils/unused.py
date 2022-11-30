import pandas as pd
from dataclasses import dataclass
from datetime import datetime, timedelta
from spot_price import TZ


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
