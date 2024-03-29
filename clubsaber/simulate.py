#!/usr/bin/env python3

from .club import Club
from .beatsaber import EventType, LightValue
from pygame import mixer

import asyncio
import json
import logging
import os
import re


class Simulation(object):
    def __init__(self, song):
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger('pywizlight').setLevel(logging.INFO)

        self.time = 0
        self.song_time = 0
        self.club = Club()

        if os.path.isdir(song):
            song = os.path.join(song, 'info.dat')

        self.song_dir, _ = os.path.split(song)
        self.info = self._load(song)
        self.bpm = self.info['beatsPerMinute']
        self.custom = self.info.get('customData', {})

        for bmset in self.info['difficultyBeatmapSets']:
            for bm in bmset['difficultyBeatmaps']:
                beatmap = bm['beatmapFilename']
                self.beatmap = self._load(os.path.join(self.song_dir, beatmap))
                self.custom.update(bm.get('customData', {}))
                break
            else:
                continue
            break

    def _load(self, filename):
        with open(filename) as file:
            return self._process(json.load(file))

    lunder = re.compile('^_')
    def _process(self, obj):
        if type(obj) is dict:
            return { re.sub(self.lunder, '', k): self._process(v) for k, v in obj.items() }
        elif type(obj) is list:
            return [self._process(item) for item in obj]
        else:
            return obj

    async def init(self):
        mixer.init()
        song_filename = self.info['songFilename']
        mixer.music.load(os.path.join(self.song_dir, song_filename))

        await self.club._init_lights()

        start_info = {
            'status': {
                'songBPM': self.bpm,
                'beatmap': { k: v for k, v in self.info.items() },
            }
        }
        custom = self.info.get('customData')
        if not custom or not custom.get('envColorLeft'):
            for dbmset in self.info.get('difficultyBeatmapSets'):
                for dbm in dbmset.get('difficultyBeatmaps'):
                    custom = dbm.get('customData')
                    if custom: break
        if custom:
            env0 = custom.get('envColorLeft')
            env1 = custom.get('envColorRight')

            colors = start_info['status']['beatmap'].setdefault('color', {})
            if env0:
                colors['environment0'] = [255 * env0[k] for k in ('r', 'g', 'b')]
            if env1:
                colors['environment1'] = [255 * env1[k] for k in ('r', 'g', 'b')]

        await self.club.receive_start(start_info)

    async def demo(self):
        ''' Give a little sparkle to show how things are working '''
        await self._simulate([
            { 'time': 0, 'type': EventType.BACK_LASERS, 'value': LightValue.OFF },
            { 'time': 0, 'type': EventType.LEFT_LASERS, 'value': LightValue.OFF },
            { 'time': 0, 'type': EventType.RIGHT_LASERS, 'value': LightValue.OFF },
            { 'time': 4, 'type': EventType.LEFT_LASERS, 'value': LightValue.BLUE_FADE },
            { 'time': 4, 'type': EventType.RIGHT_LASERS, 'value': LightValue.RED_FADE },
            { 'time': 8, 'type': EventType.BACK_LASERS, 'value': LightValue.BLUE_FLASH },
            { 'time': 10, 'type': EventType.BACK_LASERS, 'value': LightValue.RED_FLASH },
            { 'time': 12, 'type': EventType.LEFT_LASERS, 'value': LightValue.RED_ON },
            { 'time': 12, 'type': EventType.RIGHT_LASERS, 'value': LightValue.BLUE_ON },
            { 'time': 16, 'type': EventType.BACK_LASERS, 'value': LightValue.BLUE_FLASH },
            { 'time': 18, 'type': EventType.BACK_LASERS, 'value': LightValue.RED_FLASH },
            { 'time': 20, 'type': EventType.LEFT_LASERS, 'value': LightValue.BLUE_FADE },
            { 'time': 20, 'type': EventType.RIGHT_LASERS, 'value': LightValue.RED_FADE },
        ])

    async def stress_test(self, bpm = 60):
        ''' Cycle a light on the beat as a test for how many operations can be performed '''
        dt = 60.0 / bpm
        types = (
            EventType.BACK_LASERS,
            EventType.RING_LIGHTS,
            EventType.LEFT_LASERS,
            EventType.RIGHT_LASERS,
        )
        light_index = 0
        try:
            while True:
                await asyncio.gather(*[
                    self.club.receive_map_event({ 'beatmapEvent': {
                        'type': types[light_index], 'value': LightValue.BLUE_FLASH,
                    }}),
                    asyncio.sleep(dt),
                ])
                light_index = (light_index + 1) % len(types)
        except KeyboardInterrupt:
            return

    async def _simulate(self, events):
        tasks = []
        self.time = 0

        if not events:
            try:
                self._emulate(events)
            except Exception as e:
                print(e)

        for event in events:
            ets = event.get('time', 0)
            if ets > self.time:
                dt = (ets - self.time) / self.bpm * 60.0
                await asyncio.sleep(dt)

                if mixer.music.get_busy():
                    new_song_time = mixer.music.get_pos()
                    self.time += (new_song_time - self.song_time) / 1000 * self.bpm / 60
                    self.song_time = new_song_time
                else:
                    self.time = ets

            tasks.append(asyncio.create_task(
                self.club.receive_map_event({ 'beatmapEvent': event })
            ))

        asyncio.gather(*tasks)

    def _emulate(self, events):
        import random

        notes = self.beatmap.get('notes', [])
        for note in notes:
            if random.random() < 0.666:
                if note.get('cutDirection', 0) % 2 == 0:
                    et = int(EventType.LEFT_LASERS)
                else:
                    et = int(EventType.RIGHT_LASERS)
            else:
                et = int(random.choice([
                    EventType.BACK_LASERS,
                    EventType.RING_LIGHTS,
                    EventType.ROAD_LIGHTS,
                    EventType.BOOST_LIGHTS
                ]))

            if note.get('type', 0) == 0:
                lv = int(random.choice([
                    LightValue.BLUE_ON,
                    LightValue.BLUE_FLASH,
                    LightValue.BLUE_FADE
                ]))
            else:
                lv = int(random.choice([
                    LightValue.RED_ON,
                    LightValue.RED_FLASH,
                    LightValue.RED_FADE
                ]))

            events.append({ 'time': note.get('time', 0), 'type': et, 'value': lv })

    async def play(self):
        try:
            mixer.music.play()
            self.song_time = mixer.music.get_pos()

            await self._simulate(self.beatmap.get('events', []))

            await self.club.receive_end({})

        except:
            mixer.music.stop()
            await self.club.go_ambient()

