#!/usr/bin/env python3

from utils import config, log
from threading import Thread
from utils.sensors import mqtt_sensor


def my_import(name):
    components = name.split('.')
    mod = __import__(components[0])
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod


def run_sensors():
    threads = []
    with open('config/sensors.json') as cf:
        conf = config(cf)
        for name, sensor_conf in conf.sources.items():
            actor = mqtt_sensor(conf, name)
            if actor.sensor_ok():
                thread = Thread(target=actor.run,
                                daemon=True,
                                name=f'{name}_thread')
                threads.append(thread)

    for thread in threads:
        print(f'Starting thread {thread.name}')
        thread.start()

    print('Threads started')

    for thread in threads:
        thread.join()


run_sensors()
