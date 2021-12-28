import json
import os

import appdirs

from .beatsaber import EventType


class Config(object):
    def __init__(self, **values):
        self.config = dict()

        config_dir = appdirs.user_config_dir()
        try:
            with open(os.path.join(config_dir, 'club-saber.json')) as config_file:
                self.config = json.load(config_file)
        except FileNotFoundError:
            pass

        self.config.update(**values)

        self._set_defaults()

    def _set_defaults(self):
        host = self.config.setdefault('host', 'localhost')
        port = self.config.setdefault('port', 6557)
        self.config.setdefault('uri', 'ws://%s:%d/socket' % (host, port))

        self.config.setdefault('netmask', '192.168.1.255')

    def get(self, key, default=None):
        return self.config.get(key, default)

    _light_events = [
        EventType.BACK_LASERS,
        EventType.RING_LIGHTS,
        EventType.LEFT_LASERS,
        EventType.RIGHT_LASERS,
        EventType.ROAD_LIGHTS,
        EventType.BOOST_LIGHTS,
        EventType.CUSTOM_LIGHT_2,
        EventType.CUSTOM_LIGHT_3,
        EventType.CUSTOM_LIGHT_4,
        EventType.CUSTOM_LIGHT_5,
        EventType.CUSTOM_EVENT_1,
        EventType.CUSTOM_EVENT_2,
    ]

    def get_lights_for_event(self, lights: list, event):
        if event not in self._light_events:
            return []

        ignored = self.get('lights_ignored', [])
        lights = filter(lambda l: l.mac not in ignored, lights)

        mapping = self.get('light_event_map', {})
        lights = filter(lambda l: l.mac not in mapping or event in mapping[l.mac], lights)

        return lights

