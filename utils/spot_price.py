#!/usr/bin/env python3

from . import log
from .mqtt_client import hass_client, hass_topic, server_info
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


class PriceList:
    cache_timeout_s = 6 * 3600
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
        p = pd.read_json(self.cache, typ='series').tz_localize('UTC')
        self.prices = p.tz_convert(TIME_ZONE)

    def get_prices(self):
        log('Updating price list')
        use_cache = self.cache_age().total_seconds() < self.cache_timeout_s
        if use_cache:
            log('reading price list')
            self.cache_read()
        else:
            log('fetching price list')
            self.prices = self.service.get_prices()
            self.cache_write()

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
            self.get_prices()
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
        query = self.client.query_day_ahead_prices(country_code, start, end)
        return query

    def get_prices(self):
        """The price list seems to be given in Greenwich time zone,
           so must convert index to time zone."""
        query_result = self.fetch()
        price_series = parsers.parse_prices(query_result)[self.meter]
        price_series.index = price_series.index.tz_convert(TIME_ZONE)
        return price_series


def create_client():
    client = hass_client()
    client.server = server_info(address='192.168.10.200')
    client.topics['pub'] = \
        hass_topic('homeassistant/power/price/info', False, 0)
    client.topics['available'] = \
        hass_topic('homeassistant/power/price/online', False, 0)
    log(client.topics)
    return client


def run_client():
    price_list = PriceList('prices.json', Entsoe())
    client = create_client()
    client.connect()
    while True:
        try:
            try:
                price_list.update()
            except Exception as e:
                log(e)
                log('Failed to update price list. Sleeping for 5 minutes.')
                client.pub('available', 'offline')
                time.sleep(5*60)
                continue
            price = price_list.current_price()
            consumer_size = price_list.current_ranking()
            message = {'price': price, 'slot': consumer_size}
            client.pub('pub', json.dumps(message))
            client.pub('available', 'online')
            log(str(message))
            time.sleep(30)
        except (Exception, KeyboardInterrupt, SystemExit) as e:
            print(e)
            client.disconnect()
            break


def test():
    price_list = PriceList('prices.json', Entsoe())
    price_list.update()

    print(price_list.current_price())
    print(price_list.current_ranking())
