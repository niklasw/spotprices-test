#!/usr/bin/env python3

from utils.spot_price import PriceList, Entsoe
from utils.mqtt_client import hass_client, hass_topic, server_info
from utils import log
import json
import time
from threading import Thread
# import sys


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

    daemon = Thread(target=run_client,
                    daemon=True,
                    name='mqtt_client')
    daemon.run()
