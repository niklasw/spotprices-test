#!/usr/bin/env python3

from . import log, config
from .mqtt_client import mqtt_worker
import time
import json
import requests

try:
    from w1thermsensor import W1ThermSensor
    W1_SENSORS_OK = True
except Exception as e:
    W1_SENSORS_OK = False
    log(e)


class MyTemperatureException(Exception):
    def __init__(self, message='Temperature exception raised'):
        super().__init__(message=message)


class http_sensors:

    def __init__(self, name_url_map: dict):
        self.url_map = config.inv(name_url_map)
        self.parser = self.parse_temperature

    def parse_temperature(self, json_dict: dict):
        for tname in ('temperature', 'temp', 'temp:'):
            if tname in json_dict:
                return json_dict[tname]

    def get_temperatures(self):
        result = {}
        for url, name in self.url_map.items():
            try:
                r = requests.get(url)
            except Exception:
                log(f'http_sensors requests exception for sensor {name}')
                continue
            if r.status_code == 200:
                try:
                    json_response = r.json()
                except Exception as e:
                    log(f'http_sensors error for sensor {name}'
                        f'from {url}. {e}')
                    continue
                temp = self.parser(json_response)
                if temp:
                    result[name] = temp
            else:
                log(f'http_sensors: Request error from {url} '
                    f'with status {r.status_code}')
        return result

    def json(self):
        return json.dumps(self.get_values())


class w1_sensors:

    def __init__(self, device_map: dict):
        self.kernel_ok = W1_SENSORS_OK
        self.device_map = config.inv(device_map)

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

    def json(self):
        return json.dumps(self.get_temperatures())


class mqtt_sensors(mqtt_worker):

    exception_delay = 5*60
    execution_delay = 5*60

    type_map = {'w1': w1_sensors,
                'http': http_sensors,
                }

    def __init__(self, conf: config):
        super().__init__(conf)
        for sensor_type, value in conf.sources.items():
            sensor_class = self.type_map[sensor_type]
            sensor_conf = conf.sources[sensor_type]
            self.sources.append(sensor_class(sensor_conf))

    def action(self):
        result = {}
        for s in self.sources:
            result = {**result, **(s.get_temperatures())}
        if result:
            self.client.pub('available', 'online')
            self.client.pub('temperatures', json.dumps(result))
            log(json.dumps(result))
            time.sleep(self.execution_delay)
        else:
            self.client.pub('available', 'offline')
            log('temperature sensors offline')
            time.sleep(self.exception_delay)


def test():
    CONFIG = config(open('config/sensors.json'))
    worker = mqtt_sensors(CONFIG)
    worker.run()
