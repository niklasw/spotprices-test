#!/usr/bin/env python3

from . import log
import paho.mqtt.client as mqtt
from dataclasses import dataclass
import signal
import time
import sys


@dataclass
class server_info:
    address: str = '192.168.10.200'
    port: int = 1883
    protocol: str = 'tcp'


@dataclass
class hass_topic:
    topic: str = '$SYS/#'
    retain: bool = False
    qos: int = 0

    def __repr__(self):
        return f'{self.topic}, retain = {self.retain}, QoS = {self.qos}'


class hass_client(mqtt.Client):
    debug = False

    def __init__(self):
        super().__init__()
        self.server = server_info()
        self.topics: dict = {'sys': hass_topic(),
                             'available': hass_topic(topic='$SYS/available'),
                             'pub': None}
        self.QoS: int = 1

    def connect(self):
        try:
            super().connect(self.server.address, self.server.port, keepalive=60)
        except:
            log('Can not connect to mqtt server.')
            sys.exit(1)
        self.pub('available', 'online')

    def on_connect(self, client, userdata, flags, rc):
        log(f'Connected. Result code {str(rc)}')

    def on_disconnect(self, client, userdata, rc):
        log(f'Disconnecting. Result code {str(rc)}')

    def on_message(self, client, userdata, msg):
        log(f'Got message regarding {msg.topic} - {msg.payload}')

    def pub(self, topic_name, payload):
        topic = self.topics[topic_name]
        self.publish(topic.topic,
                     payload=payload,
                     qos=topic.qos,
                     retain=topic.retain)

    def disconnect(self):
        self.pub('available', 'offline')
        super().disconnect()


if __name__ == '__main__':
    def signal_handler(signal, frame):
        print('Exiting')
        client.disconnect()
        time.sleep(1)
        sys.exit(0)

    client = hass_client()
    client.debug = True
    client.topics['available'] = \
        hass_topic(topic='homeassistant/test/available', retain=False, qos=0)
    client.topics['test'] = \
        hass_topic(topic='homeassistant/test/topic', retain=False, qos=0)
    client.connect()
    signal.signal(signal.SIGINT, signal_handler)
    for i in range(10):
        client.pub('test', i)
        time.sleep(0.1)
    client.pub('test', '----------------')
    client.disconnect()

    # client.loop_forever()
