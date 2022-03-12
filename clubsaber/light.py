import asyncio
import colorsys
import itertools

from . import logger


class Light(object):
    @staticmethod
    async def discover(config):
        lights = []

        async for light in Light._discover_hue(config):
            lights.append(light)

        async for light in Light._discover_wiz(config):
            lights.append(light)

        return lights

    async def update(**state):
        raise NotImplementedError

    @staticmethod
    async def _discover_hue(config):
        try:
            import hue, socket, requests
            for info in await hue.Bridge.discover():
                if not info.get('id') or not info.get('internalipaddress'):
                    continue

                id, ip = info['id'], info['internalipaddress']
                bridge_configs = config.get('bridges', {})
                if id not in bridge_configs:
                    # TODO: Check for ignored bridges

                    if not await self._pair_with_hue_bridge(config, id, ip):
                        continue

                bridge_config = config.get('bridges', {})[id]
                user = bridge_config['username']
                bridge = hue.Bridge(ip=ip, user=user)
                bridge_info = await bridge.get_info()

                lights = bridge_info['lights']
                light_keys = lights.keys()
                if 'group' in bridge_config:
                    for _, group_info in bridge_info.get('groups', {}).items():
                        if group_info.get('name') == bridge_config['group']:
                            light_keys = group_info.get('lights', [])

                for light_id, light_info in lights.items():
                    if light_id not in light_keys:
                        continue

                    yield HueLight(hue.Light(id=light_id, ip=ip, user=user), config)

        except ImportError:
            logger.debug('Failed to import hue. Hue lights unsupported')

    @staticmethod
    async def _pair_with_hue_bridge(config, id, ip):
        while True:
            response = input('Bridge %s discovered. Pair? [y/N]')
            if response.lower() != 'y':
                # TODO: Record this?
                return False

            handshake = requests.post('http://%s/api' % ip, json={
                'devicetype': 'club_saber#%s' % socket.gethostname()
            })
            handshake.raise_for_status()
            result = handshake.json()

            if 'error' in result:
                print(result['error']['description'])
            elif 'success' in result:
                # TODO: This won't work! I need an entry-point to write to the config
                config.bridges[id] = {
                    'username' : result['success']['username']
                }
                return True

    @staticmethod
    async def _discover_wiz(config):
        try:
            import pywizlight.discovery
            wizlights = await pywizlight.discovery.discover_lights(
                    broadcast_space=config.get('netmask'))
            for light in wizlights:
                yield WizLight(light, config)
        except ImportError:
            logger.debug('Failed to import pywizlight. WiZ lights unsupported')


class HueLight(Light):
    def __init__(self, huelight, config):
        self.light = huelight
        self.config = config

    async def update(self, **state):
        await self.light.set_state(self.translate(**state))

    @staticmethod
    def translate(on=True, rgb=(255, 255, 255), brightness=0.0, speed=0.5):
        h, s, v = colorsys.rgb_to_hsv(*rgb)
        return {
            'on': on and v > 0,
            'bri': max(1, min(254, v)),
            'hue': int(h * 65535),
            'sat': int(s * 254),
            'bri_inc': int(254 * max(-1.0, min(1.0, brightness))),
            'transitiontime': int((1.0 - speed) * 50),
        }


class WizLight(Light):
    def __init__(self, wizlight, config):
        self.light = wizlight
        self.config = config

    async def update(self, on=True, **state):
        if on:
            await self.light.turn_on(self.translate(**state))
        else:
            await self.light.turn_off()

    @staticmethod
    def translate(on=True, rgb=(255, 255, 255), brightness=0.0, speed=0.5):
        from pywizlight import PilotBuilder

        h, s, v = colorsys.rgb_to_hsv(*rgb)
        pilot = PilotBuilder(
            rgb = tuple(map(self._round_color, rgb)),
            brightness = v * max(0.0, min(1.0, brightness)),
            speed = int(max(0.0, min(1.0, speed)) * 100),
        )

        # Fuck this shit. This isn't for club lighting :laughing:
        pilot.pilot_params.pop('c', None)
        pilot.pilot_params.pop('w', None)

        logger.debug('Pilot: %s', pilot.__dict__)

        return pilot

    @staticmethod
    def _round_color(value):
        return min(255, round(value / 128) * 128)

