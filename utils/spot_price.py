#!/usr/bin/env python3

from . import log, config
from .mqtt_client import mqtt_publisher
import os
from datetime import datetime, timedelta
from dateutil import tz
from entsoe import EntsoeRawClient, parsers
from pathlib import Path
import time
import json
import pandas as pd

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

    def current_price(self):
        """Filter out current hourly price from price list"""
        now = datetime.now(TZ)
        today = self.prices[self.prices.index.day == now.day]
        price = today[today.index.hour == now.hour].values[0]
        try:
            float(price)
            return price
        except ValueError:
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


class mqtt_spot_price(mqtt_publisher):

    def __init__(self, conf: config):
        super().__init__(conf)
        self.price_list = PriceList('prices.json', Entsoe())

    def action(self):
        try:
            self.price_list.update()
        except Exception as e:
            log(e)
            log('mqtt_spot_price: Failed to update price list.'
                f'Sleeping for {self.exception_delay/60} minutes.')
            self.client.pub('available', 'offline')
            time.sleep(self.exception_delay)
            return
        if not self.price_list.prices.empty:
            message = {'price': self.price_list.current_price(),
                       'slot': self.price_list.current_ranking()}
            self.client.pub('pub', json.dumps(message))
            self.client.pub('available', 'online')
            log(str(message))
            time.sleep(self.execution_delay)


def test():
    CONFIG = config(open('config/spot_price.json'))
    worker = mqtt_spot_price(CONFIG)
    worker.run()
