from .beatsaber import Network, EventType, LightValue
from .config import Config
from .color import Color, WHITE, RED, GREEN, BLUE, YELLOW
from . import logger
from pywizlight import PilotBuilder, discovery
import asyncio
import json
import random
import websockets


OFF = 0
LOW = 64
MED = 128
HI = 192
V_HI = 255


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
        self.lights = await discovery.discover_lights(broadcast_space=self.netmask)
        if not self.lights:
            raise RuntimeError('Unable to find any wiz lights. Have you done your setup?')
        print('Discovered %d lights: %s' %
              (len(self.lights), [light.mac for light in self.lights]))

    async def init(self):
        await asyncio.gather(
            self._init_game(),
            self._init_lights())

    async def enter_game(self):
        self.celebrating = False
        await self.go_dim()

    async def go_dim(self):
        await asyncio.gather(*[
            light.turn_on(self.red.get_pilot(brightness = LOW, speed = 20))
            for light in self.lights])

    async def go_ambient(self):
        await asyncio.gather(*[
            light.turn_on(YELLOW.get_pilot(brightness = HI, speed = 40))
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

            self.red = Color.from_beatsaber(colors['environment0']) if 'environment0' in colors else RED
            self.blue = Color.from_beatsaber(colors['environment1']) if 'environment1' in colors else BLUE

            # TODO: Boost / sabers?

            logger.info('Using nearest colors: %s', [self.red, self.blue])
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
                   light.turn_off() if idx == off_light_idx else
                    light.turn_on(YELLOW.get_pilot(brightness = HI, speed = 90))
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
        'SSS': WHITE.copy( brightness = 0.75 ),
        'SS':  WHITE.copy( brightness = 0.75 ),
        'S':   WHITE.copy( brightness = 0.75 ),
        'A':   GREEN.copy( brightness = 0.75 ),
        'B':   GREEN.copy( brightness = 0.5  ),
        'C':   YELLOW.copy(brightness = 0.5  ),
        'D':   YELLOW.copy(brightness = 0.5  ),
        'E':   YELLOW.copy(brightness = 0.25 ),
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
                    tasks.append(light.turn_on(rank.get_pilot(brightness = 255, speed = 40)))
                    continue

                color = random.choice([self.red, self.blue])
                pilot = color.get_pilot(
                    brightness = random.randrange(MED, V_HI),
                    speed = random.randrange(40, 90)
                )
                tasks.append(light.turn_on(pilot))

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
            await light.turn_off()
        elif value == LightValue.RED_ON:
            await light.turn_on(self.red.get_pilot( brightness = MED, speed = 80))
        elif value == LightValue.BLUE_ON:
            await light.turn_on(self.blue.get_pilot(brightness = MED, speed = 80))
        elif value == LightValue.RED_FADE:
            await light.turn_on(self.red.get_pilot( brightness = HI,  speed = 80))
            await light.turn_on(self.red.get_pilot( brightness = LOW, speed = 20))
        elif value == LightValue.BLUE_FADE:
            await light.turn_on(self.blue.get_pilot(brightness = HI,  speed = 80))
            await light.turn_on(self.blue.get_pilot(brightness = LOW, speed = 20))
        elif value == LightValue.RED_FLASH:
            await light.turn_on(self.red.get_pilot( brightness = HI,  speed = 80))
            await light.turn_on(self.red.get_pilot( brightness = MED, speed = 40))
        elif value == LightValue.BLUE_FLASH:
            await light.turn_on(self.blue.get_pilot(brightness = HI,  speed = 80))
            await light.turn_on(self.blue.get_pilot(brightness = MED, speed = 40))

    handlers = {
        'hello': receive_hello,
        'songStart': receive_start,
        'finished': receive_end,
        'pause': receive_pause,
        'resume': receive_resume,
        'beatmapEvent': receive_map_event,
    }

