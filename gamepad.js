
const GamepadStatus = {
    UNSUPPORTED: 0,
    CONFLICT: 1,
    DISCONNECTED: 2,
    CONNECTED: 3,
    IDLE: 4,
}

// must be aligned w/ enum in file "../web.py"
const GamepadKeys = {
    // analog sticks (dpad is considered to be an axis !)
    LEFT_AXIS_X: "lx",
    LEFT_AXIS_Y: "ly",
    LEFT_AXIS_BT: "lb",
    RIGHT_AXIS_X: "rx",
    RIGHT_AXIS_Y: "ry",
    RIGHT_AXIS_BT: "rb",

    DPAD_AXIS_X: "dy",
    DPAD_AXIS_Y: "dx",

    // shoulder triggers
    LEFT_TRIGGER: "lt",
    LEFT_BUMPER: "lm",
    RIGHT_TRIGGER: "rt",
    RIGHT_BUMPER: "rm",

    // buttons
    BUTTON_X: "x",
    BUTTON_Y: "y",
    BUTTON_A: "a",
    BUTTON_B: "b",

    // other
    HOME: "h",
    BACK: "k",
    START: "s",

    // holy cross (for conversions, dpad is nonexistent in the browser)
    DPAD_UP: "u",
    DPAD_DOWN: "d",
    DPAD_LEFT: "l",
    DPAD_RIGHT: "r"
}

// gamepad.id ==> "20d6-2005-Generic X-Box pad"
// lsusb ==> Bus 003 Device 029: ID 20d6:2005 PowerA Xbox Series X Wired Controller OPP Black
// TODO: check that this mapping is consistent through browsers
const PowerAButtonMapping = {
    0: GamepadKeys.BUTTON_A,
    1: GamepadKeys.BUTTON_B,
    2: GamepadKeys.BUTTON_X,
    3: GamepadKeys.BUTTON_Y,
    4: GamepadKeys.LEFT_BUMPER,
    5: GamepadKeys.RIGHT_BUMPER,
    6: GamepadKeys.BACK,
    7: GamepadKeys.START,
    8: GamepadKeys.HOME, // ??? not sure
    9: GamepadKeys.LEFT_AXIS_BT,
    10: GamepadKeys.RIGHT_AXIS_BT
}

const PowerAAxisMapping = {
    0: GamepadKeys.LEFT_AXIS_X,
    1: GamepadKeys.LEFT_AXIS_Y,
    2: GamepadKeys.LEFT_TRIGGER,
    3: GamepadKeys.RIGHT_AXIS_X,
    4: GamepadKeys.RIGHT_AXIS_Y,
    5: GamepadKeys.RIGHT_TRIGGER,
    6: GamepadKeys.DPAD_AXIS_X,
    7: GamepadKeys.DPAD_AXIS_Y,
}

const SteamDeckButtonMapping = {
    0: GamepadKeys.BUTTON_A,
    1: GamepadKeys.BUTTON_B,
    2: GamepadKeys.BUTTON_X,
    3: GamepadKeys.BUTTON_Y,
    4: GamepadKeys.LEFT_BUMPER,
    5: GamepadKeys.RIGHT_BUMPER,
    6: GamepadKeys.LEFT_TRIGGER, // analog
    7: GamepadKeys.RIGHT_TRIGGER, // analog
    8: GamepadKeys.BACK,
    9: GamepadKeys.START,
    10: GamepadKeys.LEFT_AXIS_BT,
    11: GamepadKeys.RIGHT_AXIS_BT,
    12: GamepadKeys.DPAD_UP,
    13: GamepadKeys.DPAD_DOWN,
    14: GamepadKeys.DPAD_LEFT,
    15: GamepadKeys.DPAD_RIGHT,
    16: GamepadKeys.HOME // ??? not sure
}

const SteamDeckAxisMapping = {
    0: GamepadKeys.LEFT_AXIS_X,
    1: GamepadKeys.LEFT_AXIS_Y,
    2: GamepadKeys.RIGHT_AXIS_Y, // These two are INVERTED, because
    3: GamepadKeys.RIGHT_AXIS_X  // Aru needs them in this order.
}

// Gamepad identification under Steam Deck
const _steamDeckGamepadVendorID = "28de";
const _steamDeckGamepadProductID = "11ff";
class GamepadHandler {


    /**
     * Gamepad class, handles only one gamepad
     * @param {*} sendCallback Will be called with a json payload describing the gamepad state.
     * @param {*} statusCallback Will be called with a GamepadStatus describing the gamepad status.
     * @param {*} parentWindow The browser's window
     * @param {*} gamepadIdleMS Delay before the gamepad is considered idle
     * @param {*} axisMinValue Minimum threshold value to detect analog movement (min = 0, max = 1)
     */
    constructor(sendCallback, statusCallback, parentWindow, gamepadIdleMS = 5000, axisMinValue = 0.5) {
        this._sendCallback = sendCallback;
        this._statusCallback = statusCallback;
        this._gamepadIdleMS = gamepadIdleMS;
        this._axisMinValue = axisMinValue;
        this._parentWindow = parentWindow;
        this._rafID = null; // Request Animation Frame ID
        this._prevGamepadString = null;
        this._lastGamepadTS = 0;
    }

    /**
     * Will poll the gamepad state (once detected)
     */
    start() {
        this._polling = true;
        this._parentWindow.addEventListener("gamepadconnected", event => {
            let str = `[GAMEPAD] A gamepad was connected: ${event.gamepad.id}`;
            console.log(str);
            this._statusCallback(GamepadStatus.CONNECTED);

            // TODO: detect "UNSUPPORTED" status

            // start the initial gamepad loop iteration (if not started yet)
            if (!this._rafID) {
                this._pollGamepads();
            }
        });

        this._parentWindow.addEventListener("gamepaddisconnected", event => {
            let str = `[GAMEPAD] A gamepad was disconnected: ${event.gamepad.id}`;
            console.log(str);
            this._statusCallback(GamepadStatus.DISCONNECTED);
        });
    }

    /**
     * Stops polling the gamepad state
     */
    stop() {
        this._polling = false;
    }

    _vibrate(gamepad, duration = 50) {
        if (!gamepad.vibrationActuator) {
            return;
        }
        gamepad.vibrationActuator.playEffect("dual-rumble", {
            startDelay: 0,
            duration: duration,
            weakMagnitude: 1.0,
            strongMagnitude: 1.0,
        });
    }

    _pollGamepads() {
        // Always call `navigator.getGamepads()` inside of the game loop, not outside.
        const gamepads = navigator.getGamepads().filter(obj => Boolean(obj));
        if (gamepads.length != 1) {
            if (gamepads.length > 1) {
                this._statusCallback(GamepadStatus.CONFLICT);
            } else {
                this._statusCallback(GamepadStatus.DISCONNECTED);
            }
            return;
        }
        else {
            let send_anyway = false;
            let index = 0;
            let gamepad_json = {};
            const gamepad = gamepads[0];
            const is_steam_deck = gamepad.id.includes("Vendor: " + _steamDeckGamepadVendorID) &&
                                gamepad.id.includes("Product: " + _steamDeckGamepadProductID);
            const axis_mapping = is_steam_deck ? SteamDeckAxisMapping : PowerAAxisMapping;
            const button_mapping = is_steam_deck ? SteamDeckButtonMapping : PowerAButtonMapping;

            for (const gamepad of gamepads) {
                if (gamepad) {
                    gamepad_json = {};

                    // digital stuff: buttons
                    gamepad.buttons.forEach((button, index) => {
                        gamepad_json[button_mapping[index]] = button.pressed ? 1 : 0;
                        if (button.pressed) {
                            this._vibrate(gamepad);
                            console.log("BUTTON:" + index + " - " + button_mapping[index]);
                        }
                    });

                    // analog stuff: sticks, dpad, triggers
                    let gp = this;
                    gamepad.axes.forEach((axis, index) => {
                        // we have to convert the dpad (as axis) to dpad (as button)
                        if (axis_mapping[index] === GamepadKeys.DPAD_AXIS_X) {
                            gamepad_json[GamepadKeys.DPAD_LEFT] = (axis === -1) ? -1 : 0;
                            gamepad_json[GamepadKeys.DPAD_RIGHT] = (axis === 1) ? 1 : 0;
                        }
                        else if (axis_mapping[index] === GamepadKeys.DPAD_AXIS_Y) {
                            gamepad_json[GamepadKeys.DPAD_UP] = (axis === -1) ? 1 : 0;
                            gamepad_json[GamepadKeys.DPAD_DOWN] = (axis === 1) ? 1 : 0;
                        }
                        else {
                            // get axis value
                            gamepad_json[axis_mapping[index]] = (axis > -(this._axisMinValue) && axis < this._axisMinValue) ? 0 : axis;

                            // if we push the axis to its max value, the json payload will be sent only once,
                            // because we send only the payload when it changes: the robot won't move !
                            // so we're making an exception here :)
                            send_anyway = (Math.abs(axis) === 1)
                        }
                    });
                }
                index++;
            }

            // send to websocket only if changes occurred, avoids spamming
            let gamepad_str = JSON.stringify(gamepad_json);
            if(send_anyway === true || this._prevGamepadString != gamepad_str) {
                this._sendCallback({"j" : gamepad_json});
                this._statusCallback(GamepadStatus.CONNECTED);
                this._prevGamepadString = gamepad_str
                this._lastGamepadTS = Date.now();
            }

            if (Date.now() - this._lastGamepadTS > this._gamepadIdleMS) {
                this._statusCallback(GamepadStatus.IDLE);
            }

            if(this._polling === true) {
                this._rafID = this._parentWindow.requestAnimationFrame(() => this._pollGamepads());
            }
        }
    }
}
