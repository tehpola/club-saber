#!/usr/bin/env python3

from .club import Club
from pygame import mixer

import asyncio
import json
import os
import re


class Simulation(object):
    def __init__(self, song):
        self.time = 0
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
                'beatmap': {
                    'color': {
                    }
                }
            }
        }
        custom = self.info.get('customData')
        if custom:
            env0 = custom.get('envColorLeft')
            env1 = custom.get('envColorRight')

            if env0:
                r, g, b = env0['r'], env0['g'], env0['b']
                start_info['status']['beatmap']['color']['environment0'] = [r, g, b]
            if env1:
                r, g, b = env1['r'], env1['g'], env1['b']
                start_info['status']['beatmap']['color']['environment1'] = [r, g, b]

        await self.club.receive_start(start_info)

    async def play(self):
        mixer.music.play()

        tasks = []
        events = self.beatmap.get('events', [])
        for event in events:
            ets = event.get('time', 0)
            if ets > self.time:
                dt = (ets - self.time) / self.bpm * 60.0
                await asyncio.sleep(dt) # TODO: Imperfect - I should try to sync with the song
                self.time = ets

            tasks.append(asyncio.create_task(
                self.club.receive_map_event({ 'beatmapEvent': event })
            ))

        asyncio.gather(*tasks)

        await self.club.receive_end({})

