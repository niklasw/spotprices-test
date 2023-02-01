#!/usr/bin/env python3

from . import log, config
import paho.mqtt.client as mqtt
from dataclasses import dataclass
import sys
import time


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
            super().connect(self.server.address, self.server.port,
                            keepalive=60)
        except Exception:
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
        self.loop_stop()
        super().disconnect()

    def loop(self):
        super().loop_forever()


class mqtt_publisher(hass_client):

    exception_delay = 5*60
    execution_delay = 5*60

    def __init__(self, conf: config):
        super().__init__()
        self.server = server_info(**conf.server)
        self.conf = conf

    def read(self, name: str):
        conf = self.conf.sources[name]
        self.type_name = conf['type']
        self.type_conf = conf['sensors']
        self.topics['pub'] = hass_topic(topic=conf['topic'])
        self.topics['available'] = hass_topic(topic=conf['available'])
        self.execution_delay = \
            conf.get('update_period') or self.exception_delay
        self.exception_delay = \
            conf.get('retry_period') or self.execution_delay

    def action(self):
        return False

    def run(self):
        self.connect()
        self.loop_start()
        while True:
            try:
                if self.action():
                    time.sleep(self.execution_delay)
                else:
                    log('mqtt_publisher.action returned nothing')
                    self.offline()
                    time.sleep(self.exception_delay)
            except (KeyboardInterrupt, SystemExit):
                self.offline()
                break
        self.loop_stop()
        self.disconnect()

    def offline(self):
        self.pub('available', 'offline')
