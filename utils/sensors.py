#!/usr/bin/env python3

from . import log
import json
import requests

try:
    from w1thermsensor import W1ThermSensor
except Exception as e:
    W1_SENSORS_OK = False
    log(e)


class http_sensors:

    def __init__(self, url_name_map: dict):
        self.url_name_map = url_name_map

    def parse_temperature(self, json_dict: dict):
        for tname in ('temperature', 'temp', 'temp:'):
            if tname in json_dict:
                return json_dict[tname]

    def get_temperatures(self):
        result = {}
        for url, name in self.url_name_map.items():
            temperature = -1000
            r = requests.get(url)
            if r.status_code == 200:
                try:
                    json_response = r.json()
                except Exception as e:
                    log(f'Result error from {url}. {e}')
                temp = self.parse_temperature(json_response)
                if temp:
                    temperature = temp
            else:
                log(f'Request error from {url} with status {r.status_code}')
            result[name] = temperature
        return result

    def json(self):
        return json.dumps(self.get_values())


class w1_sensors:

    def __init__(self, id_name_map):
        self.kernel_ok = W1_SENSORS_OK
        self.id_name_map = id_name_map

    def get_temperatures(self):
        result = {}
        for s in W1ThermSensor.get_available_sensors():
            if s.id in self.id_name_map:
                name = self.id_name_map[s.id]
                result[name] = s.get_temperature()
        return result

    def json(self):
        return json.dumps(self.get_temperatures())


def test():
    w1_map = {'3c01b607b5a1': 'pool_pipes',
              '3c01b607ee7e': 'pool_water'}
    http_map = {'https://minglarn.se/ha_sensor.php': 'minglarn_weather'}

    result = {}
    if W1_SENSORS_OK:
        w1 = w1_sensors(w1_map).get_temperatures()
        result = {**result, **w1}

    http = http_sensors(http_map).get_temperatures()
    result = {**result, **http}
    print(json.dumps(result, indent=4))
