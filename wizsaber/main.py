from pywizlight import wizlight, PilotBuilder, discovery
from .beatsaber import Network, EventType, LightValue
import asyncio
import websockets
import json


LOW = 64
MID = 128
HI = 192
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
BLUE = (0, 0, 255)


class Club(object):
    def __init__(self):
        self.color_0 = RED
        self.color_1 = BLUE

    async def init(self, game_uri, network):
        self.game_uri = game_uri
        self.packet_size = Network.MAX_PACKET_SIZE
        print('Attempting to connect to Beat Saber (%s)...' % self.game_uri)
        self.game = await websockets.connect(
                game_uri, max_size=self.packet_size)

        self.lights = await discovery.discover_lights(broadcast_space=network)
        if not self.lights:
            raise RuntimeError('Unable to find any wiz lights. Have you done your setup?')
        print('Discovered %d lights: %s' %
              (len(self.lights), [light.mac for light in self.lights]))

    async def enter_game(self):
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
            except websockets.exceptions.ConnectionClosedError as e:
                print('Caught exception: %s' % e)

                self.packet_size *= 2
                print('Attempting to reconnect with a larger packet size (%d)'
                      % self.packet_size)

                self.game = await websockets.connect(
                        self.game_uri, max_size=self.packet_size)

    def report_status(self, data):
        bm = data.get('status', {}).get('beatmap')
        if not bm:
            return

        print('%s%s by %s (%s)' % (
            bm.get('songName', 'UNKNOWN'),
            ' [%s]' % bm['songSubName'] if bm.get('songSubName') else '',
            bm.get('songAuthorName', 'UNKNOWN'),
            bm.get('difficulty')))

    def process_environment(self, data):
        colors = data.get('status', {}).get('beatmap', {}).get('color')
        if not colors:
            return

        self.color_0 = colors.get('environment0', RED)
        self.color_1 = colors.get('environment1', BLUE)
        # TODO: Boost / sabers?

        print('Colors: %s' % ((self.color_0, self.color_1)))

    async def receive_hello(self, data):
        print('Hello Beat Saber!')
        self.report_status(data)

    async def receive_start(self, data):
        self.report_status(data)
        await self.enter_game()

    async def receive_end(self, data):
        await self.go_ambient()

    async def receive_pause(self, data):
        # TODO: Save state for resume?
        await self.go_ambient()

    async def receive_resume(self, data):
        await self.enter_game()

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
            await light.turn_on(PilotBuilder(rgb = self.color_0, brightness = HI, speed = 80))
        elif value == LightValue.BLUE_ON:
            await light.turn_on(PilotBuilder(rgb = self.color_1, brightness = HI, speed = 80))
        elif value == LightValue.RED_FADE:
            await light.turn_on(PilotBuilder(rgb = self.color_0, brightness = LOW, speed = 20))
        elif value == LightValue.BLUE_FADE:
            await light.turn_on(PilotBuilder(rgb = self.color_1, brightness = LOW, speed = 20))
        elif value == LightValue.RED_FLASH:
            await light.turn_on(PilotBuilder(rgb = self.color_0, brightness = HI, speed = 80))
            await light.turn_on(PilotBuilder(rgb = self.color_0, brightness = LOW, speed = 40))
        elif value == LightValue.BLUE_FLASH:
            await light.turn_on(PilotBuilder(rgb = self.color_1, brightness = HI, speed = 80))
            await light.turn_on(PilotBuilder(rgb = self.color_1, brightness = LOW, speed = 40))

    handlers = {
        'hello': receive_hello,
        'songStart': receive_start,
        'finished': receive_end,
        'pause': receive_pause,
        'resume': receive_resume,
        'beatmapEvent': receive_map_event,
    }


async def main(uri, network):
    club = Club()
    await club.init(uri, network)
    await club.run()


if __name__ == '__main__':
    # TODO: Break out to a config
    asyncio.run(main('ws://CA04385W.local:6557/socket', '192.168.11.255'))

