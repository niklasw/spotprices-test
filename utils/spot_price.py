#!/usr/bin/env python3

from . import log
import os
from datetime import datetime, timedelta
from dateutil import tz
from pathlib import Path
try:
    import pandas as pd
    from entsoe import EntsoeRawClient, parsers
    ENTSOE_OK = True
except Exception as e:
    ENTSOE_OK = False
    log(e)

TIME_ZONE = 'Europe/Stockholm'
TZ = tz.gettz(TIME_ZONE)


def day_start(time: datetime):
    return datetime(time.year, time.month, time.day, 0, 0, 0, 0, TZ)


class MyEntsoeException(Exception):
    def __init__(self, message='Entsoe exception raised'):
        super().__init__(message=message)


class PriceList:
    cache_timeout_s = 8 * 3600
    default_price = 1000
    max_usage_hours = 24

    def __init__(self, cache_file, service):
        self.cache: Path = Path(cache_file)
        self.service = service
        self.query_result = None
        self.prices: pd.TimeSeries = None
        self.last_updated = datetime.now(TZ) - timedelta(days=1)
        self.update_interval = timedelta(hours=4)

    def cache_age(self):
        if self.cache.exists():
            st_mtime = self.cache.stat().st_mtime
        else:
            st_mtime = 0
        return datetime.now(TZ) - datetime.fromtimestamp(st_mtime, TZ)

    def cache_write(self):
        if self.prices is not None:
            self.prices.to_json(self.cache)

    def cache_read(self):
        try:
            p = pd.read_json(self.cache, typ='series').tz_localize('UTC')
        except Exception:
            log('cache_read failed')
            return None
        return p.tz_convert(TIME_ZONE)

    def get_prices(self):
        log('Updating price list')
        use_cache = self.cache_age().total_seconds() < self.cache_timeout_s
        new_prices = None
        if use_cache:
            log('reading price list')
            new_prices = self.cache_read()
        else:
            log('fetching price list')
            try:
                new_prices = self.service.get_prices()
            except MyEntsoeException as e:
                log(f'get_prices failed with {e}')
        if new_prices is not None:
            self.prices = new_prices
            if not use_cache:
                self.cache_write()
            return True

    def get_daily_prices(self, today=False):
        groups = self.prices.groupby(self.prices.index.day)
        # groupby returns a list of tuples (date, series), so filter out
        # the actual series.
        if today:
            for g in groups:
                if g[0] == datetime.now(TZ).day:
                    return g[1]
        return [g[1] for g in groups]

    def update(self):
        if (datetime.now(TZ) - self.last_updated) > self.update_interval:
            if self.get_prices():
                self.last_updated = datetime.now(TZ)
            else:
                return {}
        p_now = self.instant_price(datetime.now(TZ))
        try:
            p_fut = self.instant_price(datetime.now(TZ) + timedelta(hours=12))
        except:
            p_fut = self.default_price
        slot = self.current_ranking()
        return {'price': p_now, 'slot': slot, 'future_price': p_fut}

    def current_price(self):
        return self.instant_price(datetime.now(TZ))

    def instant_price(self, now):
        """Filter out current hourly price from price list"""
        today = self.prices[self.prices.index.day == now.day]
        price = today[today.index.hour == now.hour].values[0]
        try:
            float(price)
            return price
        except ValueError:
            log(f'ValueError {price}')
            return self.default_price

    def todays_sorted(self):
        today_pricelist = self.get_daily_prices(today=True)
        return today_pricelist.sort_values()

    def current_ranking(self):
        hour = datetime.now(TZ).hour
        for i, item in enumerate(self.todays_sorted().items()):
            if item[0].hour == hour:
                return i
        return 24


class Entsoe:
    def __init__(self):
        self.meter = '60T'
        API_KEY = os.getenv('ENTSOE_API_KEY')
        self.client = EntsoeRawClient(api_key=API_KEY)

    def fetch(self):
        start = pd.Timestamp(datetime.now(), tz=TIME_ZONE)
        end = pd.Timestamp(datetime.now() + timedelta(days=1),
                           tz=TIME_ZONE)
        country_code = 'SE_3'
        try:
            query = \
                self.client.query_day_ahead_prices(country_code, start, end)
        except Exception:
            raise MyEntsoeException
        return query

    def get_prices(self):
        """The price list seems to be given in Greenwich time zone,
           so must convert index to time zone."""
        query_result = self.fetch()
        if query_result is not None:
            price_series = parsers.parse_prices(query_result)[self.meter]
            price_series.index = price_series.index.tz_convert(TIME_ZONE)
            return price_series
        return None


class entsoe_price_list(PriceList):
    ok = ENTSOE_OK

    def __init__(self, conf: dict):
        cache_file = conf['0']['cache']
        super().__init__(cache_file, Entsoe())
