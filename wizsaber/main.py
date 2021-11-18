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

LV_OFF = 0
LV_BLUE_ON = 1
LV_BLUE_FLASH = 2
LV_BLUE_FADE = 3
LV_RED_ON = 5
LV_RED_FLASH = 6
LV_RED_FADE = 7


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

    async def enter_game(self):
        for light in self.lights:
            await light.turn_on(PilotBuilder(rgb = YELLOW, brightness = LOW, speed = 40))

    async def go_ambient(self):
        for light in self.lights:
            await light.turn_on(PilotBuilder(rgb = YELLOW, brightness = HI, speed = 60))

    async def run(self):
        while True:
            packet = await self.game.recv()
            data = json.loads(packet)

            handler = self.handlers.get(data.get('event'))
            if handler:
                await handler(self, data)

    async def receive_hello(self, data):
        print('Hello Beat Saber!')
        print(data)

    async def receive_start(self, data):
        await self.enter_game()

    async def receive_end(self, data):
        await self.go_ambient()

    async def receive_pause(self, data):
        await self.go_ambient()

    async def receive_resume(self, data):
        await self.enter_game()

    async def receive_map_event(self, data):
        event = data.get('beatmapEvent', {})
        etype = event.get('type')
        value = event.get('value')

        light = None
        if etype in (0, 1, 4, 5):
            light = self.lights[0]
        elif etype == 2:
            light = self.lights[1]
        elif etype == 3:
            light = self.lights[2]

        if not light:
            return

        if value == LV_OFF:
            await light.turn_on(PilotBuilder(rgb = YELLOW, brightness = LOW, speed = 80))
        elif value == LV_RED_ON:
            await light.turn_on(PilotBuilder(rgb = RED, brightness = HI, speed = 80))
        elif value == LV_BLUE_ON:
            await light.turn_on(PilotBuilder(rgb = BLUE, brightness = HI, speed = 80))
        elif value == LV_RED_FADE:
            await light.turn_on(PilotBuilder(rgb = RED, brightness = LOW, speed = 20))
        elif value == LV_BLUE_FADE:
            await light.turn_on(PilotBuilder(rgb = BLUE, brightness = LOW, speed = 20))
        elif value == LV_RED_FLASH:
            await light.turn_on(PilotBuilder(rgb = RED, brightness = HI, speed = 80))
            await light.turn_on(PilotBuilder(rgb = RED, brightness = LOW, speed = 40))
        elif value == LV_BLUE_FLASH:
            await light.turn_on(PilotBuilder(rgb = BLUE, brightness = HI, speed = 80))
            await light.turn_on(PilotBuilder(rgb = BLUE, brightness = LOW, speed = 40))

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


async def main(uri, network):
    club = Club()
    await club.init(uri, network)
    await club.run()


if __name__ == '__main__':
    # TODO: Break out to a config
    asyncio.run(main('ws://CA04385W.local:6557/socket', '192.168.11.255'))

