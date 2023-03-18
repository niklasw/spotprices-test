
from . import file_age, log
from .sensors import general_sensors, http_parsers
from pathlib import Path
import json
import os


class currency_sensor(general_sensors):
    cache_timeout_s = 12 * 3600
    ok = False

    def __init__(self, conf: dict):
        super().__init__(conf)
        self.cache = Path(conf.get('cache', 'db/exchange_rate.json'))
        self.api_key = os.getenv('EXCHANGE_RATES_API_KEY')
        if self.api_key:
            self.ok = True
        print(self.api_key)

    def cache_read(self):
        with self.cache.open() as fp:
            try:
                return json.load(fp)
            except json.JSONDecodeError:
                log(f'currency_sensor failed reading cache {self.cache}')

    def cache_write(self, data: json):
        with self.cache.open('w') as fp:
            json.dump(fp, data)

    def get_x_rate(self):
        result = {}
        for url, name in self.device_map.items():
            http_tool = http_parsers(url, name)
            http_tool.headers = {'apikey': self.api_key}
            use_cache = file_age(self.cache).total_seconds() \
                < self.cache_timeout_s
            if use_cache:
                json_data = self.cache_read()
            else:
                if json_data := http_tool.fetch_json():
                    self.cache_write(json_data)
            parser = http_tool.select()
            parsed = parser(json_data)
            if parsed:
                result = parsed
            else:
                log(f'curency_sensor returned nothing from {name}')
        return result

    def get_values(self):
        return self.get_x_rate()
