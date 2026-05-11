from enum import IntEnum


class AncMode(IntEnum):
    OFF          = 0
    TRANSPARENCY = 1
    ANC          = 2


class GainLevel(IntEnum):
    LOW  = 0
    HIGH = 1


class SidetoneLevel(IntEnum):
    OFF    = 0
    LOW    = 1
    MEDIUM = 2
    HIGH   = 3


class AudioOutput(IntEnum):
    SPEAKERS = 1
    STREAM   = 2


class HomeScreenMode(IntEnum):
    DETAILED = 0
    SIMPLE   = 1


class WirelessMode(IntEnum):
    PERFORMANCE    = 0
    EXTENDED_RANGE = 1


class ConnectivityMode(IntEnum):
    WIRELESS_ONLY   = 0x01   # 2.4 GHz wireless link only
    BT_PAIRING      = 0x02   # Bluetooth pairing mode active
    WIRELESS_AND_BT = 0x04   # 2.4 GHz wireless + Bluetooth active


class BtAutoMute(IntEnum):
    OFF        = 0
    DB_MINUS_12 = 1
    FULL       = 2


class TimeoutStep(IntEnum):
    OFF        = 0
    ONE_MIN    = 1
    FIVE_MIN   = 2
    TEN_MIN    = 3
    FIFTEEN_MIN = 4
    THIRTY_MIN = 5
    SIXTY_MIN  = 6
