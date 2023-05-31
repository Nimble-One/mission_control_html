import json
from enum import Enum

import numpy as np

import nimbleone.core

# ------------------------------------------------------------------------------
# must be aligned w/ enum in file "./js/gamepad.js"
class GamepadKey(Enum):
    # analog sticks
    LEFT_STICK_X = "lx"
    LEFT_STICK_Y = "ly"
    LEFT_STICK_BT = "lb"
    RIGHT_STICK_X = "rx"
    RIGHT_STICK_Y = "ry"
    RIGHT_STICK_BT = "rb"

    # shoulder triggers
    LEFT_TRIGGER = "lt"
    LEFT_BUMPER = "lm"
    RIGHT_TRIGGER = "rt"
    RIGHT_BUMPER = "rm"

    # holy cross
    DPAD_UP = "u"
    DPAD_DOWN = "d"
    DPAD_LEFT = "l"
    DPAD_RIGHT = "r"

    # buttons
    BUTTON_X = "x"
    BUTTON_Y = "y"
    BUTTON_A = "a"
    BUTTON_B = "b"

    # other
    BACK = "k"
    START = "s"
    HOME = "h"

# ------------------------------------------------------------------------------
class GamepadHandler():
    def update_gamepad_slot(gamepad_json: json, slot: nimbleone.core.Slot):
        def value_of(gkey: GamepadKey):
            key = gkey.value
            return gamepad_json[key] if key in gamepad_json else 0

        gamepad_data = np.array(
            [
                value_of(GamepadKey.LEFT_STICK_X),
                value_of(GamepadKey.LEFT_STICK_Y),
                value_of(GamepadKey.RIGHT_STICK_X),
                value_of(GamepadKey.RIGHT_STICK_Y),
                value_of(GamepadKey.BUTTON_A),
                value_of(GamepadKey.BUTTON_B),
                value_of(GamepadKey.BUTTON_X),
                value_of(GamepadKey.BUTTON_Y),
                value_of(GamepadKey.LEFT_BUMPER),
                value_of(GamepadKey.RIGHT_BUMPER),
                value_of(GamepadKey.LEFT_TRIGGER),
                value_of(GamepadKey.RIGHT_TRIGGER),
                value_of(GamepadKey.BACK),
                value_of(GamepadKey.START),
                value_of(GamepadKey.DPAD_UP),
                value_of(GamepadKey.DPAD_DOWN),
                value_of(GamepadKey.DPAD_LEFT),
                value_of(GamepadKey.DPAD_RIGHT),
            ]
        )
        with nimbleone.core.write(slot) as w:
            w.write(gamepad_data)
