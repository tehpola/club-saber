import colorsys
import logging

from pywizlight import PilotBuilder


class Color(object):
    def __init__(self, rgb, **kwargs):
        self.rgb = rgb
        self.brightness = 1.0
        self.__dict__.update(kwargs)

    @staticmethod
    def _round_color(value):
        return min(255, round(value / 128) * 128)

    @staticmethod
    def from_beatsaber(rgb):
        h, s, v = hsv = colorsys.rgb_to_hsv(*rgb)

        logging.debug('Beatsaber %s; HSV %s', rgb, hsv)

        rgb = tuple(map(Color._round_color, rgb))
        return Color(rgb, brightness = v / 255)

    def get_pilot(self, brightness = 128, speed = 50):
        pilot = PilotBuilder(
            rgb = self.rgb,
            brightness = brightness * self.brightness,
            speed = speed,
        )

        # Fuck this shit. This isn't for club lighting :laughing:
        pilot.pilot_params.pop('c', None)
        pilot.pilot_params.pop('w', None)

        #logging.debug('Pilot: %s', pilot.__dict__)

        return pilot

    def copy(self, **kwargs):
        result = Color(None)
        result.__dict__.update(self.__dict__)
        result.__dict__.update(kwargs)
        return result

    def __repr__(self):
        return 'Color(%s)' % self.__dict__


WHITE   = Color((255, 255, 255))
RED     = Color((255, 0,   0  ))
GREEN   = Color((0,   255, 0  ))
BLUE    = Color((0,   0,   255))
FUSCHIA = Color((255, 0,   255))
YELLOW  = Color((255, 255, 0  ))

