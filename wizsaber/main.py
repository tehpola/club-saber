from .beatsaber import Network, EventType, LightValue
from pywizlight import PilotBuilder, discovery
import appdirs
import asyncio
import json
import os
import random
import websockets


OFF = 0
LOW = 64
MED = 128
HI = 192
V_HI = 255

# WiZ is a bit limited in color selection...
BLACK   = (0,   0,   0)
WHITE   = (255, 255, 255)
RED     = (255, 0,   0)
GREEN   = (0,   255, 0)
BLUE    = (0,   0,   255)
TEAL    = (0,   255, 255)
FUSCHIA = (255, 0,   255)
YELLOW  = (255, 255, 0)
COLORS = [
    BLACK,
    RED, GREEN, BLUE,
    TEAL, FUSCHIA, YELLOW,
    WHITE,
]


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

        self.bpm = 60/0.666
        self.color_0 = RED
        self.color_1 = BLUE

        self.celebrating = False

    async def _init_game(self):
        self.packet_size = Network.MAX_PACKET_SIZE
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
            light.turn_on(PilotBuilder(rgb = YELLOW, brightness = LOW, speed = 20))
            for light in self.lights])

    async def go_ambient(self):
        await asyncio.gather(*[
            light.turn_on(PilotBuilder(rgb = YELLOW, brightness = HI, speed = 40))
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

    @staticmethod
    def find_nearest(color):
        r, g, b = color
        best_color = YELLOW
        best_dist_sq = 1e6

        for near_color in COLORS:
            ncr, ncg, ncb = near_color
            dist_sq = (r - ncr)**2 + (g - ncg)**2 + (b - ncb)**2
            if dist_sq < best_dist_sq:
                best_color = near_color
                best_dist_sq = dist_sq

        return best_color

    def process_environment(self, data):
        status = data.get('status') or {}
        beatmap = status.get('beatmap') or {}

        colors = beatmap.get('color')
        if colors:
            print('Colors: %s' % colors)

            # Find similar colors supported by WiZ
            self.color_0 = self.find_nearest(colors.get('environment0', RED))
            self.color_1 = self.find_nearest(colors.get('environment1', BLUE))
            # TODO: Boost / sabers?

            print('Using nearest colors: %s' % [self.color_0, self.color_1])
        else:
            self.color_0 = RED
            self.color_1 = BLUE

        self.bpm = status.get('songBPM', 60/0.666)

    async def receive_hello(self, data):
        print('Hello Beat Saber!')
        self.report_status(data)
        self.process_environment(data)

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
        dt = 60 / self.bpm

        rank = self.rankings.get(performance.get('rank', 'E'))

        print('Yay! We got an %s (%d)!' % (
            performance.get('rank'), performance.get('score', -1)))

        tasks = []

        score_light_idx = 0

        while self.celebrating:
            for idx, light in enumerate(self.lights):
                if idx == score_light_idx:
                    tasks.append(light.turn_on(PilotBuilder(speed = 40, **rank)))
                    continue

                color = random.choice([self.color_0, self.color_1])
                brightness = random.randrange(MED, V_HI)
                speed = random.randrange(40, 90)
                tasks.append(
                    light.turn_on(PilotBuilder(rgb = color, brightness = brightness, speed = speed)))

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
            await light.turn_off()
        elif value == LightValue.RED_ON:
            await light.turn_on(PilotBuilder(rgb = self.color_0, brightness = MED, speed = 80))
        elif value == LightValue.BLUE_ON:
            await light.turn_on(PilotBuilder(rgb = self.color_1, brightness = MED, speed = 80))
        elif value == LightValue.RED_FADE:
            await light.turn_on(PilotBuilder(rgb = self.color_0, brightness = HI,  speed = 80))
            await light.turn_on(PilotBuilder(rgb = self.color_0, brightness = LOW, speed = 20))
        elif value == LightValue.BLUE_FADE:
            await light.turn_on(PilotBuilder(rgb = self.color_1, brightness = HI,  speed = 80))
            await light.turn_on(PilotBuilder(rgb = self.color_1, brightness = LOW, speed = 20))
        elif value == LightValue.RED_FLASH:
            await light.turn_on(PilotBuilder(rgb = self.color_0, brightness = HI,  speed = 80))
            await light.turn_on(PilotBuilder(rgb = self.color_0, brightness = MED, speed = 40))
        elif value == LightValue.BLUE_FLASH:
            await light.turn_on(PilotBuilder(rgb = self.color_1, brightness = HI,  speed = 80))
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

