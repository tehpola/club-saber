from .beatsaber import Network, EventType, LightValue
from pywizlight import PilotBuilder, discovery
import appdirs
import asyncio
import json
import os
import random
import websockets


LOW = 64
MED = 128
HI = 192
V_HI = 255
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
BLUE = (0, 0, 255)


class Club(object):
    def __init__(self):
        config_dir = appdirs.user_config_dir()
        config = dict()
        try:
            with open(os.path.join(config_dir, 'wizsaber.json')) as config_file:
                config = json.load(config_file)
        except FileNotFoundError:
            print('No configuration file found. Using defaults...')

        host = config.setdefault('host', 'localhost')
        port = config.setdefault('port', 6557)
        self.game_uri = config.setdefault('uri', 'ws://%s:%d/socket' % (host, port))
        self.netmask = config.setdefault('netmask', '192.168.1.255')

        self.color_0 = RED
        self.color_1 = BLUE

        self.celebrating = False

    async def init(self):
        self.packet_size = Network.MAX_PACKET_SIZE
        print('Attempting to connect to Beat Saber (%s)...' % self.game_uri)
        self.game = await websockets.connect(
                self.game_uri, max_size=self.packet_size)

        self.lights = await discovery.discover_lights(broadcast_space=self.netmask)
        if not self.lights:
            raise RuntimeError('Unable to find any wiz lights. Have you done your setup?')
        print('Discovered %d lights: %s' %
              (len(self.lights), [light.mac for light in self.lights]))

    async def enter_game(self):
        self.celebrating = False
        await self.go_dim()

    async def go_dim(self):
        for light in self.lights:
            await light.turn_on(PilotBuilder(rgb = YELLOW, brightness = LOW, speed = 40))

    async def go_ambient(self):
        for light in self.lights:
            await light.turn_on(PilotBuilder(rgb = YELLOW, brightness = HI, speed = 60))

    async def run(self):
        while True:
            try:
                packet = await self.game.recv()
                data = json.loads(packet)

                handler = self.handlers.get(data.get('event'))
                if handler:
                    await handler(self, data)

            # Packet overruns will cause the connection to be closed; try again
            except websockets.exceptions.ConnectionClosed as e:
                print('Caught exception: %s' % e)

                # TODO: Validate the code before doing this...
                self.packet_size *= 2
                print('Attempting to reconnect with a larger packet size (%d)'
                      % self.packet_size)

                # TODO: Back off if this keeps happening; don't lock up
                self.game = await websockets.connect(
                        self.game_uri, max_size=self.packet_size)

    def report_status(self, data):
        status = data.get('status') or {}
        bm = status.get('beatmap')
        if not bm:
            return

        print('%s%s by %s (%s)' % (
            bm.get('songName', 'UNKNOWN'),
            ' [%s]' % bm['songSubName'] if bm.get('songSubName') else '',
            bm.get('songAuthorName', 'UNKNOWN'),
            bm.get('difficulty')))

    def process_environment(self, data):
        status = data.get('status') or {}
        beatmap = status.get('beatmap') or {}
        colors = beatmap.get('color')
        if not colors:
            return

        print('Colors: %s' % colors)

        # TODO: Find similar colors supported by WiZ
        #self.color_0 = colors.get('environment0', RED)
        #self.color_1 = colors.get('environment1', BLUE)
        # TODO: Boost / sabers?

    async def receive_hello(self, data):
        print('Hello Beat Saber!')
        self.report_status(data)
        self.process_environment(data)

    async def receive_start(self, data):
        self.report_status(data)
        self.process_environment(data)
        await self.enter_game()

    async def receive_end(self, data):
        perf = data.get('performance') or {}
        if perf and not perf.get('softFailed', False):
            asyncio.create_task(self.celebrate(perf))
        else:
            self.celebrating = False

            await self.go_ambient()

    rankings = {
        'SSS': { 'rgb': WHITE,  'brightness': HI },
        'SS':  { 'rgb': WHITE,  'brightness': HI },
        'S':   { 'rgb': WHITE,  'brightness': HI },
        'A':   { 'rgb': GREEN,  'brightness': HI },
        'B':   { 'rgb': GREEN,  'brightness': MED },
        'C':   { 'rgb': YELLOW, 'brightness': MED },
        'D':   { 'rgb': YELLOW, 'brightness': MED },
        'E':   { 'rgb': YELLOW, 'brightness': LOW },
    }
    async def celebrate(self, performance):
        self.celebrating = True

        rank = self.rankings.get(performance.get('rank', 'E'))

        print('Yay! We got an %s (%d)!' % (performance.get('rank'), performance.get('score')))

        await self.lights[0].turn_on(PilotBuilder(speed = 40, **rank))

        while self.celebrating:
            for light in self.lights[1:]:
                color = random.choice([self.color_0, self.color_1])
                brightness = random.randrange(MED, V_HI)
                speed = random.randrange(40, 90)
                await light.turn_on(PilotBuilder(rgb = color, brightness = brightness, speed = speed))

            await asyncio.sleep(0.666)

    async def receive_pause(self, data):
        print('Pausing...')

        # TODO: Save state for resume?

        await self.go_ambient()

    async def receive_resume(self, data):
        print('Let\'s get back in there!')

        await self.go_dim()

        # TODO: Restore state?

    async def receive_map_event(self, data):
        event = data.get('beatmapEvent', {})
        etype = event.get('type')
        value = event.get('value')

        light = None
        if etype in (EventType.BACK_LASERS, EventType.RING_LIGHTS,
                     EventType.ROAD_LIGHTS, EventType.BOOST_LIGHTS):
            light = self.lights[0]
        elif etype == EventType.LEFT_LASERS:
            light = self.lights[1]
        elif etype == EventType.RIGHT_LASERS:
            light = self.lights[2]

        if not light:
            return

        if value == LightValue.OFF:
            await light.turn_on(PilotBuilder(rgb = YELLOW, brightness = LOW, speed = 80))
        elif value == LightValue.RED_ON:
            await light.turn_on(PilotBuilder(rgb = self.color_0, brightness = MED, speed = 80))
        elif value == LightValue.BLUE_ON:
            await light.turn_on(PilotBuilder(rgb = self.color_1, brightness = MED, speed = 80))
        elif value == LightValue.RED_FADE:
            await light.turn_on(PilotBuilder(rgb = self.color_0, brightness = HI, speed = 80))
            await light.turn_on(PilotBuilder(rgb = self.color_0, brightness = LOW, speed = 20))
        elif value == LightValue.BLUE_FADE:
            await light.turn_on(PilotBuilder(rgb = self.color_1, brightness = HI, speed = 80))
            await light.turn_on(PilotBuilder(rgb = self.color_1, brightness = LOW, speed = 20))
        elif value == LightValue.RED_FLASH:
            await light.turn_on(PilotBuilder(rgb = self.color_0, brightness = HI, speed = 80))
            await light.turn_on(PilotBuilder(rgb = self.color_0, brightness = MED, speed = 40))
        elif value == LightValue.BLUE_FLASH:
            await light.turn_on(PilotBuilder(rgb = self.color_1, brightness = HI, speed = 80))
            await light.turn_on(PilotBuilder(rgb = self.color_1, brightness = MED, speed = 40))

    handlers = {
        'hello': receive_hello,
        'songStart': receive_start,
        'finished': receive_end,
        'pause': receive_pause,
        'resume': receive_resume,
        'beatmapEvent': receive_map_event,
    }


async def main():
    club = Club()
    await club.init()
    await club.run()


if __name__ == '__main__':
    asyncio.run(main())

