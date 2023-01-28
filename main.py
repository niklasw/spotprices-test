#!/usr/bin/env python3

from utils import config, log
from threading import Thread
try:
    from utils.sensors import mqtt_sensor
except ImportError:
    log('mqtt_sensor module failed')
try:
    from utils.spot_price import mqtt_spot_price
except ImportError:
    log('mqtt_spot_price module failed')

loaded_modules = dir()


def run_threads():
    threads = []
    with open('config/sensors.json') as cf:
        conf = config(cf)
        if 'mqtt_spot_price' in loaded_modules:
            spot_price = mqtt_spot_price(conf, 'entsoe')
            spot_price.exception_delay = 60

            p1 = Thread(target=spot_price.run,
                        daemon=True,
                        name='spot_price_client')
            threads.append(p1)

        if 'mqtt_sensor' in loaded_modules:
            w1_sensors = mqtt_sensor(conf, 'w1')
            http_sensors = mqtt_sensor(conf, 'http')
            w1_sensors.execution_delay = 60
            http_sensors.execution_delay = 5*60

            t1 = Thread(target=w1_sensors.run,
                        daemon=True,
                        name='w1_client')
            threads.append(t1)

            t2 = Thread(target=http_sensors.run,
                        daemon=True,
                        name='http_client')
            threads.append(t2)

    for thread in threads:
        print(f'Starting thread {thread.name}')
        thread.start()

    print('Threads started')

    for thread in threads:
        thread.join()


run_threads()
