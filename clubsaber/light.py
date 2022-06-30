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

    def get_id(self):
        raise NotImplementedError

    @staticmethod
    async def _discover_hue(config):
        try:
            import hue
            bridge_configs = config.get('bridges', {})
            if not bridge_configs:
                for info in await hue.Bridge.discover():
                    logger.info(info)
                    if not info.get('id') or not info.get('internalipaddress'):
                        continue

                    id, ip = info['id'], info['internalipaddress']
                    if id not in bridge_configs:
                        # TODO: Check for ignored bridges

                        if not await Light._pair_with_hue_bridge(config, id, ip):
                            continue

            for id, bridge_config in bridge_configs.items():
                user = bridge_config['username']
                ip = bridge_config['ip']
                bridge = hue.Bridge(ip=ip, user=user)
                bridge_info = await bridge.get_info()
                logger.debug('Bridge Info: %s' % bridge_info)

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
        import requests, socket

        while True:
            response = input('Bridge %s discovered. Pair? [y/N]' % id)
            if response.lower() != 'y':
                # TODO: Record this?
                return False

            handshake = requests.post('http://%s/api' % ip, json={
                'devicetype': 'club_saber#%s' % socket.gethostname()
            })
            logger.debug(handshake, handshake.text)
            handshake.raise_for_status()
            result = handshake.json()

            if any('error' in obj for obj in result):
                print(*[obj['error']['description'] for obj in result])
            elif any('success' in obj for obj in result):
                # TODO: This won't work! I need an entry-point
                #   to write to the config
                bridges = config.get('bridges', {})
                bridge_config = bridges.setdefault(id, {})
                bridge_config['ip'] = ip
                bridge_config['username'] = result[0]['success']['username']
                config.set('bridges', bridges)
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

    def get_id(self):
        return self.light.id

    async def update(self, **state):
        try:
            await self.light.set_state(self.translate(**state))
        except Exception as e:
            print(e)
            pass # FIXME: Seems like we timeout a lot... :thinking:

    @staticmethod
    def translate(on=True, rgb=(255, 255, 255), brightness=1.0, speed=0.5):
        h, s, v = colorsys.rgb_to_hsv(*rgb)
        v = int(brightness * v)
        return {
            'on': on and v > 0,
            'bri': max(1, min(254, v)),
            'hue': int(h * 65535),
            'sat': int(s * 254),
            #'bri_inc': int(254 * max(-1.0, min(1.0, brightness))),
            'transitiontime': int((1.0 - speed) * 5),
        }


class WizLight(Light):
    def __init__(self, wizlight, config):
        self.light = wizlight
        self.config = config

    def get_id(self):
        return self.light.mac

    async def update(self, on=True, **state):
        if on:
            await self.light.turn_on(self.translate(**state))
        else:
            await self.light.turn_off()

    @staticmethod
    def translate(on=True, rgb=(255, 255, 255), brightness=1.0, speed=0.5):
        from pywizlight import PilotBuilder

        h, s, v = colorsys.rgb_to_hsv(*rgb)
        pilot = PilotBuilder(
            rgb = tuple(map(WizLight._round_color, rgb)),
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

