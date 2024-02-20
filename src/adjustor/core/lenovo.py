from .acpi import call, read
from typing import Sequence, Literal

import logging

logger = logging.getLogger(__name__)

MIN_CURVE = [44, 48, 55, 60, 71, 79, 87, 87, 100, 100]

TdpMode = Literal["quiet", "balanced", "performance", "custom"]


def get_fan_curve():
    logger.info("Retrieving fan curve.")
    o = call(r"\_SB.GZFD.WMAB", [0, 0x05, bytes([0, 0, 0, 0])])
    if not o:
        return None
    o = read()
    if not isinstance(o, bytes):
        return None

    return [o[i] for i in range(4, 44, 4)]


def set_fan_curve(arr: Sequence[int], lim: Sequence[int] | None = None):
    logger.info(f"Setting fan curve to:\n{arr}")
    if len(arr) != 10:
        logger.error(f"Invalid fan curve length: {len(arr)}. Should be 10.")
        return False

    if lim:
        for a, b in zip(arr, lim):
            if a < b:
                logger.error(
                    f"Not set. Fan curve does not comply with limit:\n{len(arr)}"
                )
                return False

    return call(
        r"\_SB.GZFD.WMAB",
        [
            0,
            0x06,
            bytes(
                [
                    0x00,
                    0x00,
                    0x0A,
                    0x00,
                    0x00,
                    0x00,
                    arr[0],
                    0x00,
                    arr[1],
                    0x00,
                    arr[2],
                    0x00,
                    arr[3],
                    0x00,
                    arr[4],
                    0x00,
                    arr[5],
                    0x00,
                    arr[6],
                    0x00,
                    arr[7],
                    0x00,
                    arr[8],
                    0x00,
                    arr[9],
                    0x00,
                    0x00,
                    0x0A,
                    0x00,
                    0x00,
                    0x00,
                    0x0A,
                    0x00,
                    0x14,
                    0x00,
                    0x1E,
                    0x00,
                    0x28,
                    0x00,
                    0x32,
                    0x00,
                    0x3C,
                    0x00,
                    0x46,
                    0x00,
                    0x50,
                    0x00,
                    0x5A,
                    0x00,
                    0x64,
                    0x00,
                    0x00,
                ]
            ),
        ],
    )


def set_power_light(enabled: bool):
    logger.info(f"Setting power light status.")
    return call(r"\_SB.GZFD.WMAF", [0, 0x02, bytes([0x03, int(enabled), 0x00])])


def get_power_light():
    logger.info(f"Getting power light status.")
    if not call(r"\_SB.GZFD.WMAF", [0, 0x01, 0x03]):
        return None
    o = read()
    if isinstance(o, bytes) and len(o) == 2:
        return bool(o[0])
    return None


def get_feature_expanded(dev: int, feature: int, type: int = 0):
    if not call(
        r"\_SB.GZFD.WMAE",
        [
            0,
            0x11,
            int.to_bytes(type, length=2, byteorder="little", signed=False)
            + bytes(
                [
                    feature,
                    dev,
                ]
            ),
        ],
    ):
        return None

    return read()


def get_feature(id: int):
    if not call(
        r"\_SB.GZFD.WMAE",
        [0, 0x11, int.to_bytes(id, length=4, byteorder="little", signed=False)],
    ):
        return None

    return read()


def set_feature(id: int, value: int):
    return call(
        r"\_SB.GZFD.WMAE",
        [
            0,
            0x12,
            int.to_bytes(id, length=4, byteorder="little", signed=False)
            + int.to_bytes(value, length=4, byteorder="little", signed=False),
        ],
    )


def set_tdp_mode(mode: TdpMode):
    logger.info(f"Setting tdp mode to '{mode}'.")
    match mode:
        case "quiet":
            b = 0x01
        case "balanced":
            b = 0x02
        case "performance":
            b = 0x03
        case "custom":
            b = 0xFF
        case _:
            logger.error(f"TDP mode '{mode}' is unknown. Not setting.")
            return False

    return call(r"\_SB.GZFD.WMAA", [0, 0x2C, b])


def get_tdp_mode() -> TdpMode | None:
    logger.info(f"Retrieving TDP Mode.")
    if not call(r"\_SB.GZFD.WMAA", [0, 0x2D]):
        logger.error(f"Failed retrieving TDP Mode.")
        return None

    match read():
        case 0x01:
            return "quiet"
        case 0x02:
            return "balanced"
        case 0x03:
            return "performance"
        case 0xFF:
            return "custom"
        case v:
            logger.error(f"TDP mode '{v}' is unknown")
            return None


def get_steady_tdp():
    logger.info(f"Retrieving steady TDP.")
    return get_feature(0x0102FF00)


def get_fast_tdp():
    logger.info(f"Retrieving fast TDP.")
    return get_feature(0x0103FF00)


def get_slow_tdp():
    logger.info(f"Retrieving slow TDP.")
    return get_feature(0x0101FF00)


def set_steady_tdp(val: int):
    logger.info(f"Setting steady TDP to {val}.")
    return set_feature(0x0102FF00, val)


def set_fast_tdp(val: int):
    logger.info(f"Setting fast TDP to {val}.")
    return set_feature(0x0103FF00, val)


def set_slow_tdp(val: int):
    logger.info(f"Setting slow TDP to {val}.")
    return set_feature(0x0101FF00, val)