from enum import IntEnum, unique


class Network(IntEnum):
    PORT            = 6557
    MAX_PACKET_SIZE = 64000000


class EventType(IntEnum):
    BACK_LASERS        = 0
    RING_LIGHTS        = 1
    LEFT_LASERS        = 2
    RIGHT_LASERS       = 3
    ROAD_LIGHTS        = 4
    BOOST_LIGHTS       = 5
    CUSTOM_LIGHT_2     = 6
    CUSTOM_LIGHT_3     = 7
    RINGS_ROTATE       = 8
    RINGS_ZOOM         = 9
    CUSTOM_LIGHT_4     = 10
    CUSTOM_LIGHT_5     = 11
    LEFT_LASERS_SPEED  = 12
    RIGHT_LASERS_SPEED = 13
    EARLY_ROTATION     = 14
    LATE_ROTATION      = 15
    CUSTOM_EVENT_1     = 16
    CUSTOM_EVENT_2     = 17


@unique
class LightValue(IntEnum):
    OFF        = 0
    BLUE_ON    = 1
    BLUE_FLASH = 2
    BLUE_FADE  = 3
    RED_ON     = 5
    RED_FLASH  = 6
    RED_FADE   = 7

