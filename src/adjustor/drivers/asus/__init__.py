import logging
import time
from typing import cast
import os

from hhd.plugins import Context, HHDPlugin, load_relative_yaml
from hhd.plugins.conf import Config
from adjustor.core.platform import get_platform_choices, set_platform_profile

logger = logging.getLogger(__name__)

APPLY_DELAY = 1.5
TDP_DELAY = 0.2

FTDP_FN = "/sys/devices/platform/asus-nb-wmi/ppt_fppt"
STDP_FN = "/sys/devices/platform/asus-nb-wmi/ppt_pl2_sppt"
CTDP_FN = "/sys/devices/platform/asus-nb-wmi/ppt_pl1_spl"

FAN_CURVE_ENDPOINT = "/sys/class/hwmon"
FAN_CURVE_NAME = "asus_custom_fan_curve"

POINTS = [30, 40, 50, 60, 70, 80, 90, 100]
MIN_CURVE = [30, 30, 30, 45, 50, 50, 50, 50]
DEFAULT_CURVE = [40, 40, 40, 50, 60, 70, 80, 90]


def set_tdp(pretty: str, fn: str, val: int):
    logger.info(f"Setting tdp value '{pretty}' to {val} by writing to:\n{fn}")
    try:
        with open(fn, "w") as f:
            f.write(f"{val}\n")
        return True
    except Exception as e:
        logger.error(f"Failed writing value with error:\n{e}")
        return False


def find_fan_curve_dir():
    for dir in os.listdir(FAN_CURVE_ENDPOINT):
        name_fn = os.path.join(FAN_CURVE_ENDPOINT, dir, "name")
        with open(name_fn, "r") as f:
            name = f.read().strip()
        print(name_fn, name)
        if name == FAN_CURVE_NAME:
            return os.path.join(FAN_CURVE_ENDPOINT, dir)
    return None


def set_fan_curve(points: list[int], curve: list[int]):
    point_str = ",".join([f"{p:> 4d} C" for p in points])
    curve_str = ",".join([f"{p:> 4d} %" for p in curve])
    logger.info(f"Setting the following fan curve:\n{point_str}\n{curve_str}")

    dir = find_fan_curve_dir()
    if not dir:
        logger.error(f"Could not find hwmon with name:\n'{FAN_CURVE_NAME}'")
        return False

    for fan in (1, 2):
        for i, (temp, speed) in enumerate(zip(points, curve)):
            print(os.path.join(dir, f"pwm{fan}_auto_point{i+1}_temp"))
            with open(os.path.join(dir, f"pwm{fan}_auto_point{i+1}_temp"), "r") as f:
                f.write(f"{temp}\n")
            with open(os.path.join(dir, f"pwm{fan}_auto_point{i+1}_pwm"), "r") as f:
                f.write(f"{speed}\n")

    for fan in (1, 2):
        with open(os.path.join(dir, f"pwm{fan}_enable"), "r") as f:
            f.write(f"2\n")

    return True


def disable_fan_curve():
    logger.info(f"Disabling custom fan curve.")

    dir = find_fan_curve_dir()
    if not dir:
        logger.error(f"Could not find hwmon with name:\n'{FAN_CURVE_NAME}'")
        return False

    for fan in (1, 2):
        with open(os.path.join(dir, f"pwm{fan}_enable"), "r") as f:
            f.write(f"0\n")

    return True


class AsusDriverPlugin(HHDPlugin):
    def __init__(self) -> None:
        self.name = f"asus"
        self.priority = 6
        self.log = "adjl"
        self.enabled = False
        self.initialized = False
        self.enforce_limits = True
        self.startup = True
        self.old_conf = None

        self.queue_fan = None
        self.queue_tdp = None

    def settings(self):
        if not self.enabled:
            self.initialized = False
            self.old_conf = None
            self.startup = True
            return {}

        self.initialized = True
        out = {"tdp": {"asus": load_relative_yaml("settings.yml")}}
        if not self.enforce_limits:
            out["tdp"]["asus"]["children"]["tdp"]["max"] = 40
        return out

    def open(
        self,
        emit,
        context: Context,
    ):
        pass

    def update(self, conf: Config):
        self.enabled = conf["hhd.settings.tdp_enable"].to(bool)
        new_enforce_limits = conf["hhd.settings.enforce_limits"].to(bool)
        new_lims = new_enforce_limits != self.enforce_limits
        self.enforce_limits = new_enforce_limits

        if not self.enabled or not self.initialized or new_lims:
            self.old_conf = None
            self.startup = True
            return

        # If not old config, exit, as values can not be set
        if not self.old_conf:
            self.old_conf = conf["tdp.asus"]
            return

        curr = time.time()

        #
        # TDP
        #

        # Reset fan curve on mode change
        # Has to happen before setting the stdp, ftdp values, in case
        # we are in custom mode
        fan_mode = conf["tdp.asus.fan.mode"].to(str)
        if fan_mode != self.old_conf["fan.mode"].to(str) and fan_mode != "manual":
            pass

        # Check user changed values
        steady = conf["tdp.asus.tdp"].to(int)

        steady_updated = steady and steady != self.old_conf["tdp"].to(int)

        if self.startup and (steady > 30 or steady < 7):
            logger.warning(
                f"TDP ({steady}) outside the device spec. Resetting for stability reasons."
            )
            steady = 30
            conf["tdp.asus.tdp"] = 30
            steady_updated = True

        boost = conf["tdp.asus.boost"].to(bool)
        boost_updated = boost != self.old_conf["boost"].to(bool)

        # If yes, queue an update
        # Debounce
        if self.startup or steady_updated or boost_updated:
            self.queue_tdp = curr + APPLY_DELAY

        if self.queue_tdp and self.queue_tdp < curr:
            if steady < 13:
                set_platform_profile("quiet")
            elif steady < 0:
                set_platform_profile("balanced")
            else:
                set_platform_profile("performance")

            self.queue_tdp = None
            if boost:
                set_tdp("steady", CTDP_FN, steady)
                time.sleep(TDP_DELAY)
                set_tdp("slow", STDP_FN, steady + 2)
                time.sleep(TDP_DELAY)
                set_tdp("fast", FTDP_FN, int(steady * 41 / 30))
            else:
                set_tdp("steady", CTDP_FN, steady)
                time.sleep(TDP_DELAY)
                set_tdp("slow", STDP_FN, steady)
                time.sleep(TDP_DELAY)
                set_tdp("fast", FTDP_FN, steady)

        # Handle fan curve resets
        if conf["tdp.asus.fan.manual.reset"].to(bool):
            conf["tdp.asus.fan.manual.reset"] = False
            for k, v in zip(POINTS, DEFAULT_CURVE):
                conf[f"tdp.asus.fan.manual.st{k}"] = v

        # Handle fan curve limits
        if conf["tdp.asus.fan.manual.enforce_limits"].to(bool):
            for k, v in zip(POINTS, MIN_CURVE):
                if conf[f"tdp.asus.fan.manual.st{k}"].to(int) < v:
                    conf[f"tdp.asus.fan.manual.st{k}"] = v

        # Check if fan curve has changed
        # Use debounce logic on these changes
        if self.startup:
            self.queue_fan = curr + 2 * APPLY_DELAY
        for i in POINTS:
            if conf[f"tdp.asus.fan.manual.st{i}"].to(int) != self.old_conf[
                f"fan.manual.st{i}"
            ].to(int):
                self.queue_fan = curr + APPLY_DELAY

        apply_curve = self.queue_fan and self.queue_fan < curr
        if apply_curve:
            try:
                if conf["tdp.asus.fan.mode"].to(str) == "manual":
                    set_fan_curve(
                        POINTS,
                        [conf[f"tdp.asus.fan.manual.st{i}"].to(int) for i in POINTS],
                    )
                else:
                    disable_fan_curve()
            except Exception as e:
                logger.error(f"Could not set fan curve. Error:\n{e}")
            self.queue_fan = None

        # Save current config
        self.old_conf = conf["tdp.asus"]

        if self.startup:
            self.startup = False

    def close(self):
        pass
