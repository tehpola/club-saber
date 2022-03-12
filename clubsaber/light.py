import asyncio
import itertools

from . import logger
#from pywizlight import PilotBuilder, discovery
#from hue import Bridge


class Light(object):
    def __init__(self):
        pass

    @staticmethod
    async def discover(config):
        return list(itertools.chain(await asyncio.gather(
            Light._discover_wiz(config),
            Light._discover_hue(config))))

    @staticmethod
    async def _discover_hue(config):
        try:
            import hue
            huelights = await hue.Bridge.discover()
            for light in huelights:
                yield HueLight(light, config)
        except ImportError:
            logger.debug('Failed to import hue. Hue lights unsupported')

    @staticmethod
    async def _discover_wiz(config):
        try:
            import pywizlight.discovery
            wizlights = await pywizlight.discovery.discover_lights(
                    broadcast_space=self.config.get('netmask'))
            for light in wizlights:
                yield WizLight(light, config)
        except ImportError:
            logger.debug('Failed to import pywizlight. WiZ lights unsupported')

    async def update(**state):
        raise NotImplementedError


class HueLight(Light):
    def __init__(self, huelight, config):
        pass


class WizLight(Light):
    def __init__(self, wizlight, config):
        pass

