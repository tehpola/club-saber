import json
import os

import appdirs


class Config(object):
    def __init__(self, **values):
        self.config = dict()

        config_dir = appdirs.user_config_dir()
        with open(os.path.join(config_dir, 'wizsaber.json')) as config_file:
            self.config = json.load(config_file)

        self.config.update(**values)

        self._set_defaults()

    def _set_defaults(self):
        host = self.config.setdefault('host', 'localhost')
        port = self.config.setdefault('port', 6557)
        self.config.setdefault('uri', 'ws://%s:%d/socket' % (host, port))

        self.config.setdefault('netmask', '192.168.1.255')

    def get(self, key, default=None):
        return self.config.get(key, default)

