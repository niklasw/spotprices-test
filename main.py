#!/usr/bin/env python3

from utils.spot_price import PriceList, Entsoe
from utils.mqtt_client import hass_client, hass_topic, server_info
from utils import log
from utils import sensors
import json
import time
from threading import Thread
# import sys


def create_tsensors_client():
    client = hass_client()
    client.server = server_info(address='192.168.10.200')
    client.topics['temperatures'] = \
        hass_topic('homeassistant/temperature/mysensors', False, 0)
    client.topics['available'] = \
        hass_topic('homeassistant/temperature/online', False, 0)
    return client


def run_tsensors():
    client = create_tsensors_client()
    client.connect()
    w1_map = {'3c01b607b5a1': 'pool_pipes',
              '3c01b607ee7e': 'pool_water'}
    http_map = {'https://minglarn.se/ha_sensor.php': 'minglarn_weather'}

    w1_s = sensors.w1_sensors(w1_map)
    http_s = sensors.http_sensors(http_map)
    while True:
        result = {}
        try:
            if w1_s.kernel_ok:
                result = {**result, **(w1_s.get_temperatures())}
            result = {**result, **(http_s.get_temperatures())}
            if result:
                client.pub('available', 'online')
                client.pub('temperatures', json.dumps(result))
                log(json.dumps(result))
            else:
                client.pub('available', 'offline')
                log('temperature sensors offline')
            time.sleep(60)
        except (Exception, KeyboardInterrupt, SystemExit) as e:
            print(e)
            client.disconnect()
            break


def create_client():
    client = hass_client()
    client.server = server_info(address='192.168.10.200')
    client.topics['pub'] = \
        hass_topic('homeassistant/power/price/info', False, 0)
    client.topics['available'] = \
        hass_topic('homeassistant/power/price/online', False, 0)
    return client


def run_client():
    global price_list
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


if __name__ == '__main__':
    price_list = PriceList('prices.json', Entsoe())

    price_daemon = Thread(target=run_client,
                          daemon=True,
                          name='mqtt_price_client')
    price_daemon.start()

    temp_daemon = Thread(target=run_tsensors,
                         daemon=True,
                         name='tsensors_client')
    temp_daemon.run()
