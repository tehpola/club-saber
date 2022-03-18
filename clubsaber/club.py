from .beatsaber import Network, EventType, LightValue
from .config import Config
from . import logger
from .light import Light
import asyncio
import json
import random
import websockets


OFF = 0
LOW = 0.25
MED = 0.5
HI = 0.75
V_HI = 1.0
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)


class Club(object):
    def __init__(self):
        self.config = Config()
        self.game_uri = self.config.get('uri')
        self.netmask = self.config.get('netmask')
        self.packet_size = Network.MAX_PACKET_SIZE

        self.bpm = 60/0.666
        self.red = RED
        self.blue = BLUE

        self.celebrating = False

        self.game = None
        self.lights = []

    async def _init_game(self):
        print('Attempting to connect to Beat Saber (%s)...' % self.game_uri)
        self.game = await websockets.connect(
                self.game_uri, max_size=self.packet_size)

    async def _init_lights(self):
        self.lights = await Light.discover(self.config)
        if not self.lights:
            raise RuntimeError('Unable to find any lights. Have you done your setup?')
        print('Discovered %d lights: %s' %
              (len(self.lights), [light.get_id() for light in self.lights]))

    async def init(self):
        await asyncio.gather(
            self._init_game(),
            self._init_lights())

    async def enter_game(self):
        self.celebrating = False
        await self.go_dim()

    async def go_dim(self):
        await asyncio.gather(*[
            light.update(rgb = self.red, brightness = LOW, speed = 0.2)
            for light in self.lights])

    async def go_ambient(self):
        await asyncio.gather(*[
            light.update(rgb = YELLOW, brightness = HI, speed = 0.4)
            for light in self.lights])

    async def run(self):
        tasks = []

        while True:
            try:
                # TODO: Report on exceptions
                tasks = [t for t in tasks if not t.done()]

                packet = await self.game.recv()
                data = json.loads(packet)

                handler = self.handlers.get(data.get('event'))
                if handler:
                    tasks.append(asyncio.create_task(
                        handler(self, data)))

            # Packet overruns will cause the connection to be closed; try again
            except websockets.exceptions.ConnectionClosed as e:
                print('Caught exception: %s' % e)

                # TODO: Validate the error code before doing this...
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
        if colors:
            print('Colors: %s' % colors)

            self.red = colors['environment0'] if 'environment0' in colors else RED
            self.blue = colors['environment1'] if 'environment1' in colors else BLUE

            # TODO: Boost / sabers?

            logger.info('Using colors: %s', [self.red, self.blue])
        else:
            self.red = RED
            self.blue = BLUE

        self.bpm = status.get('songBPM', 60/0.666)

    async def receive_hello(self, data):
        print('Hello Beat Saber!')
        self.report_status(data)
        self.process_environment(data)

        dt = 60 / 180
        for loop in range(4):
            for off_light_idx in range(len(self.lights)):
                await asyncio.gather(*[
                   light.update(on = False) if idx == off_light_idx else
                    light.update(rgb = YELLOW, brightness = HI, speed = 0.9)
                   for idx, light in enumerate(self.lights)])
                await asyncio.sleep(dt)

        await self.go_ambient()

    async def receive_start(self, data):
        self.report_status(data)
        self.process_environment(data)
        await self.enter_game()

    async def receive_end(self, data):
        status = data.get('status') or {}
        perf = status.get('performance') or {}

        if perf and not perf.get('softFailed', False):
            asyncio.create_task(self.celebrate(perf))
        else:
            self.celebrating = False

            print('Good effort!')

            await self.go_ambient()

    rankings = {
        'SSS': tuple(HI * v for v in WHITE),
        'SS':  tuple(HI * v for v in WHITE),
        'S':   tuple(HI * v for v in WHITE),
        'A':   tuple(HI * v for v in GREEN),
        'B':   tuple(MED * v for v in GREEN),
        'C':   tuple(MED * v for v in YELLOW),
        'D':   tuple(MED * v for v in YELLOW),
        'E':   tuple(LOW * v for v in YELLOW),
    }

    async def celebrate(self, performance):
        self.celebrating = True
        dt = 60 / self.bpm

        rank = self.rankings.get(performance.get('rank', 'E'))

        print('Yay! We got an %s (%d)!' % (
            performance.get('rank'), performance.get('score', -1)))

        tasks = []

        score_light_idx = 0

        while self.celebrating:
            for idx, light in enumerate(self.lights):
                if idx == score_light_idx:
                    tasks.append(light.update(rgb = rank, brightness = V_HI, speed = 0.4))
                    continue

                color = random.choice([self.red, self.blue])
                tasks.append(light.update(
                    rgb = color,
                    brightness = random.random() * (V_HI - MED) + MED,
                    speed = random.randrange(40, 90) / 100.0
                ))

            tasks.append(asyncio.sleep(dt))
            await asyncio.gather(*tasks)

            tasks.clear()
            score_light_idx = (score_light_idx + 1) % len(self.lights)

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

        lights = self.config.get_lights_for_event(self.lights, etype)
        if not lights:
            return

        await asyncio.gather(*[
            self.handle_light_event(light, value) for light in lights
        ])

    async def handle_light_event(self, light, value):
        if value == LightValue.OFF:
            await light.update(on = False)
        elif value == LightValue.RED_ON:
            await light.update(rgb = self.red, brightness = MED, speed = 0.8)
        elif value == LightValue.BLUE_ON:
            await light.update(rgb = self.blue, brightness = MED, speed = 0.8)
        elif value == LightValue.RED_FADE:
            await light.update(rgb = self.red, brightness = HI,  speed = 0.8)
            await light.update(rgb = self.red, brightness = LOW, speed = 0.2)
        elif value == LightValue.BLUE_FADE:
            await light.update(rgb = self.blue, brightness = HI,  speed = 0.8)
            await light.update(rgb = self.blue, brightness = LOW, speed = 0.2)
        elif value == LightValue.RED_FLASH:
            await light.update(rgb = self.red, brightness = HI,  speed = 0.8)
            await light.update(rgb = self.red, brightness = MED, speed = 0.4)
        elif value == LightValue.BLUE_FLASH:
            await light.update(rgb = self.blue, brightness = HI,  speed = 0.8)
            await light.update(rgb = self.blue, brightness = MED, speed = 0.4)

    handlers = {
        'hello': receive_hello,
        'songStart': receive_start,
        'finished': receive_end,
        'pause': receive_pause,
        'resume': receive_resume,
        'beatmapEvent': receive_map_event,
    }

