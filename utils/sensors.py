#!/usr/bin/env python3

from . import log, config
from .mqtt_client import hass_client, hass_topic, server_info
import time
import json
import requests

try:
    from w1thermsensor import W1ThermSensor
    W1_SENSORS_OK = True
except Exception as e:
    W1_SENSORS_OK = False
    log(e)


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
            temperature = -1000
            r = requests.get(url)
            if r.status_code == 200:
                try:
                    json_response = r.json()
                except Exception as e:
                    log(f'Result error from {url}. {e}')
                temp = self.parser(json_response)
                if temp:
                    temperature = temp
            else:
                log(f'Request error from {url} with status {r.status_code}')
            result[name] = temperature
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
                    result[name] = s.get_temperature()
        else:
            log('No w1_sensors result since kernel modules fails')
        return result

    def json(self):
        return json.dumps(self.get_temperatures())


class mqtt_sensors:

    type_map = {'w1': w1_sensors,
                'http': http_sensors,
                }

    def __init__(self, conf: config):
        self.client = hass_client()
        self.client.server = server_info(**conf.server)
        for topic, value in conf.topics.items():
            self.client.topics[topic] = hass_topic(**value)
        log(self.client.topics)

        self.sensors = []
        for sensor_type, value in conf.sensors.items():
            sensor_class = self.type_map[sensor_type]
            sensor_conf = conf.sensors[sensor_type]
            self.sensors.append(sensor_class(sensor_conf))

    def run(self):
        self.client.connect()
        self.client.loop_start()
        while True:
            result = {}
            try:
                for s in self.sensors:
                    result = {**result, **(s.get_temperatures())}
                if result:
                    self.client.pub('available', 'online')
                    self.client.pub('temperatures', json.dumps(result))
                    log(json.dumps(result))
                else:
                    self.client.pub('available', 'offline')
                    log('temperature sensors offline')
                time.sleep(60)
            except (Exception, KeyboardInterrupt, SystemExit) as e:
                print(e)
                break
        self.client.pub('available', 'offline')
        self.client.loop_stop()
        self.client.disconnect()



def test():
    CONFIG = config(open('config/sensors.json'))
    worker = mqtt_sensors(CONFIG)
    worker.run()
