
from . import log
import requests
import json

try:
    from w1thermsensor import W1ThermSensor
    W1_SENSORS_OK = True
except Exception as e:
    W1_SENSORS_OK = False
    log(e)


class MyTemperatureException(Exception):
    def __init__(self, message='Temperature exception raised'):
        super().__init__(message=message)


class temperature_sensors:
    ok = True

    def __init__(self, conf: dict):
        self.device_map = conf

    def update(self):
        return self.get_temperatures()

    def get_temperatures(self):
        return {}

    def json(self):
        return json.dumps(self.get_temperatures())


class http_parsers:

    def select(self, url):
        if 'smhi' in url:
            return self.smhi
        if 'minglarn' in url:
            return self.minglarn

    @staticmethod
    def minglarn(json_dict):
        for tname in ('temperature', 'temp', 'temp:'):
            if tname in json_dict:
                return json_dict[tname]

    @staticmethod
    def smhi_sort(json_dict):
        def sort_key(x):
            try:
                return int(x.get('date'))
            except ValueError:
                log(f'http_parsers.smhi failed to parse one item {x}')
                return 0

        if values := json_dict.get('value'):
            if isinstance(values, list) and len(values):
                sample = sorted(values, key=sort_key)[-1]
                try:
                    return float(sample['value'])
                except ValueError:
                    log(f'http_parsers.smhi failed to parse one item {sample}')
                    return None

    @staticmethod
    def smhi(json_dict):
        if values := json_dict.get('value'):
            if isinstance(values, list) and len(values):
                sample = values[-1]
                try:
                    return float(sample['value'])
                except ValueError:
                    log(f'http_parsers.smhi failed to parse one item {sample}')


class http_sensors(temperature_sensors):

    def __init__(self, conf: dict):
        super().__init__(conf)
        self.parser = self.parse_temperature

    def parse_temperature(self, json_dict: dict):
        for tname in ('temperature', 'temp', 'temp:'):
            if tname in json_dict:
                return json_dict[tname]

    def get_temperatures(self):
        result = {}
        for url, name in self.device_map.items():
            try:
                r = requests.get(url)
            except Exception:
                log(f'http_sensors requests exception for sensor {name}')
                log(f'with url = {url}')
                continue
            if r.status_code == 200:
                try:
                    json_response = r.json()
                except Exception as e:
                    log(f'http_sensors error for sensor {name}'
                        f'from {url}. {e}')
                    continue
                parser = http_parsers().select(url)
                temp = parser(json_response)
                if temp:
                    result[name] = temp
                else:
                    log(f'http_sensors parser returned nothing')
            else:
                log(f'http_sensors: Request error from {url} '
                    f'with status {r.status_code}')
        return result


class w1_sensors(temperature_sensors):
    ok = W1_SENSORS_OK

    def __init__(self, conf: dict):
        super().__init__(conf)
        self.kernel_ok = W1_SENSORS_OK

    def get_temperatures(self):
        result = {}
        if self.kernel_ok:
            for s in W1ThermSensor.get_available_sensors():
                if s.id in self.device_map:
                    name = self.device_map[s.id]
                    try:
                        result[name] = s.get_temperature()
                    except Exception:
                        log(f'w1_sensors exception for sensor {name}')
        else:
            log('No w1_sensors result since kernel modules fails')
        return result
