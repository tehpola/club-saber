import asyncio
from pywizlight import wizlight, PilotBuilder, discovery
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
        self.ambient = True
        self.r = LOW
        self.b = LOW

    async def init(self, game_uri, network):
        self.game = await websockets.connect(game_uri)

        self.lights = await discovery.discover_lights(broadcast_space=network)
        if not self.lights:
            raise RuntimeError('Unable to find any wiz lights. Have you done your setup?')
        print('Discovered %d lights: %s' % \
                (len(self.lights), [light.mac for light in self.lights]))

        self.light_r = self.lights[2]
        self.light_b = self.lights[0]
        self.lights_o = [self.lights[1]] + self.lights[3:]

    async def enter_game(self):
        await self.light_r.turn_on(PilotBuilder(rgb = RED, brightness = LOW))
        await self.light_b.turn_on(PilotBuilder(rgb = BLUE, brightness = LOW))
        for light in self.lights_o:
            await light.turn_on(PilotBuilder(rgb = YELLOW, brightness = MID))

    async def go_ambient(self):
        for light in self.lights:
            await light.turn_on(PilotBuilder(rgb = YELLOW, brightness = HI))

    async def run(self):
        while True:
            packet = await self.game.recv()
            data = json.loads(packet)

            handler = self.handlers.get(data.get('event'))
            await handler(self, data)

    async def receive_hello(self, data):
        print('Hello Beat Saber!')
        print(data)

    async def receive_start(self, data):
        self.enter_game()

    async def receive_end(self, data):
        self.go_ambient()

    async def receive_pause(self, data):
        self.go_ambient()

    async def receive_resume(self, data):
        self.enter_game()

    async def receive_map_event(self, data):
        event = data.get('beatmapEvent', {})
        type = event.get('type')
        value = event.get('value')

        if type >= 5:
            return

        if value == 0:
            # TODO: Blank
            pass
        elif value in (1, 2):
            # TODO: Turn down the blue
            pass
        elif value == 3:
            # TODO: Turn up the blue
            pass
        elif value in (5, 6):
            # TODO: Turn down the red
            pass
        elif value == 7:
            # TODO: Turn up the red
            pass

    handlers = {
        'hello': receive_hello,
        'songStart': receive_start,
        'finished': receive_end,
        'pause': receive_pause,
        'resume': receive_resume,
        'beatmapEvent': receive_map_event,
    }


async def main(uri, broadcast_space):
    lights = await discovery.discover_lights(broadcast_space=broadcast_space)
    if not lights:
        raise RuntimeError('Unable to find any wiz lights. Have you done your setup?')
    print('Discovered %d lights: %s' % (len(lights), [light.mac for light in lights]))

    async with websockets.connect(uri) as socket:
        while True:
            packet = await socket.recv()
            data = json.loads(packet)

            handler = handlers.get(data.get('event'))
            handler(lights, data)


if __name__ == '__main__':
    # TODO: Break out to a config
    asyncio.run(main('ws://CA04385W.local:6557/socket', '192.168.11.255'))

