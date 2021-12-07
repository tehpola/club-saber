import colorsys
import logging

from pywizlight import PilotBuilder


class Color(object):
    def __init__(self, rgb, **kwargs):
        self.rgb = rgb
        self.brightness = 0.5
        self.__dict__.update(kwargs)

    @staticmethod
    def from_beatsaber(rgb):
        h, s, v = hsv = colorsys.rgb_to_hsv(*rgb)

        logging.debug('Beatsaber %s; HSV %s', rgb, hsv)

        return Color(rgb, brightness = v / 255)

    def get_pilot(self, brightness = 128, speed = 50):
        pilot = PilotBuilder(
            rgb = self.rgb,
            brightness = brightness * self.brightness,
            speed = speed,
        )
        pilot._set_cold_white(1)
        pilot._set_warm_white(1)

        #logging.debug('Pilot: %s', pilot.__dict__)

        return pilot

Color.WHITE   = Color((255, 255, 255))
Color.RED     = Color((255, 0,   0  ))
Color.GREEN   = Color((0,   255, 0  ))
Color.BLUE    = Color((0,   0,   255))
Color.FUSCHIA = Color((255, 0,   255))
Color.YELLOW  = Color((255, 255, 0  ))

