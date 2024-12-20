#!/usr/bin/env python3

from . import log, err, file_age
# from .sensors import general_sensors
import os
from datetime import datetime, timedelta
from dateutil import tz
from pathlib import Path
from .price_providers import Elprisetjustnu

try:
    import pandas as pd
    ELPRISERJUSTNU_OK = True
except Exception as e:
    ELPRISERJUSTNU_OK = False
    log(e)

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


class PriceListException(Exception):
    def __init__(self, message='PriceList exception raised'):
        super().__init__(message)


# class energy_price_sensors(general_sensors):
#
#     def __init__(self, conf: dict):
#         super.__init__(conf)
#
#     def get_values(self):
#         return self.get_prices()


class TransferPrice:

    def __init__(self, conf_dict):
        """ dict must contain 'transfer_cost' with value being a list
        of pairs [[hour, price], [hour, price],...]
        Also adding energy_tax and bundle with transfer."""
        self.tariff = conf_dict.get('transfer_cost', 0)
        self.spot_add = conf_dict.get('spot_addition', 7) 
        self.tax = conf_dict.get('energy_tax', 0)
        assert isinstance(self.tariff, list)
        self.currency = 'SEK/100'
        log(conf_dict)

    def energy_tax(self):
        return self.tax

    def get(self, now: datetime):
        morning, high = self.tariff[0]
        evening, low = self.tariff[1]
        if now.month in range(4, 11):
            return low + self.spot_add
        elif now.weekday() in range(5, 7):
            return low + self.spot_add
        elif now.hour < morning or now.hour >= evening:
            return low + self.spot_add
        else:
            return high + self.spot_add

    def current_price(self):
        return self.get(datetime.now(TZ))


class PriceList:
    cache_timeout_s = 8 * 3600
    default_price = 1000
    max_usage_hours = 24
    currency_xrate = 0

    def __init__(self, conf, service):
        self.cache: Path = Path(conf.get('cache'))
        self.service = service
        self.query_result = None
        self.prices = None  # pandas series
        self.last_updated = datetime.now(TZ) - timedelta(days=1)
        self.update_interval = timedelta(seconds=4)
        self.tariff: TransferPrice = TransferPrice(conf)

    def change_currency(self, price_series):
        log(f'FIXME. Currency exchange rate {self.currency_xrate}')
        if self.currency_xrate and self.currency_xrate > 0:
            # MW -> kW and sek*100 (ore)
            price_series *= self.currency_xrate/10
        return price_series

    def cache_age(self):
        return file_age(self.cache)

    def cache_write(self, prices):
        if prices is not None:
            prices.to_json(self.cache)

    def cache_read(self):
        try:
            p = pd.read_json(self.cache, typ='series').tz_localize('UTC')
        except Exception:
            log('cache_read failed')
            return None
        return p.tz_convert(TIME_ZONE)

    def fetch_prices(self):
        log('Updating price list')
        use_cache = self.cache_age().total_seconds() < self.cache_timeout_s
        new_prices = None
        if use_cache:
            log('reading price list')
            new_prices = self.cache_read()
        else:
            log(f'fetching price list using {self.service}')
            try:
                new_prices = self.service.fetch_prices()
            except Exception as e:
                log(f'fetch_prices failed with {e}')
            self.cache_write(new_prices)
        if new_prices is not None:
            self.prices = self.change_currency(new_prices)
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

    def get_prices(self):
        now = datetime.now(TZ)
        if (now - self.last_updated) > self.update_interval:
            if self.fetch_prices():
                self.last_updated = now
            else:
                return {}
        p_now = self.instant_price(now)
        p_raw = p_now
        p_add = self.tariff.get(now)
        log(f'Current get_prices (raw) {p_now}')
        slot = self.current_ranking()
        if self.tariff:
            log('PriceList current transfer tariff plus tax '
                f'{self.tariff.get(now)} öre')
            p_now += self.tariff.get(now)
        p_now = p_now
        return {'raw': p_raw, 'add': p_add, 'price': p_now, 'slot': slot}

    def instant_price(self, now):
        """Filter out current hourly price from price list"""
        today = self.prices[self.prices.index.day == now.day]
        if today.size > 0:
            price = today[today.index.hour == now.hour].values[0]
        else:
            price = 'Price not found in time range'
        try:
            float(price)
            return price
        except ValueError as e:
            log(f'ValueError ({e})')
            return self.default_price

    def todays_sorted(self, with_tariff=True):
        today_pricelist = self.get_daily_prices(today=True)
        if with_tariff:
            for idx, value in today_pricelist.items():
                today_pricelist[idx] = value + self.tariff.get(idx.to_pydatetime())
        return today_pricelist.sort_values()

    def current_ranking(self, with_tariff=True):
        hour = datetime.now(TZ).hour
        for idx, item in enumerate(self.todays_sorted(with_tariff).items()):
            if item[0].hour == hour:
                return idx
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
        except Exception as e:
            log(f'Exception:\n{e}')
            raise PriceListException
        return query

    def fetch_prices(self):
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
        super().__init__(conf, Entsoe())
        self.subscription_topic = conf.get('subscription')
        self.shared_data = None

    def update(self):
        try:
            xrate = float(self.shared_data.get('eur_to_sek'))
        except Exception:
            xrate = self.currency_xrate
            log(f'entsoe_price_list using default currency rate {xrate}')
        self.currency_xrate = xrate
        return self.get_prices()


class elprisetjustnu_price_list(PriceList):
    ok = ELPRISERJUSTNU_OK

    def __init__(self, conf: dict):
        super().__init__(conf, Elprisetjustnu())
        self.shared_data = None
        self.subscription_topic = None

    def update(self):
        return self.get_prices()


