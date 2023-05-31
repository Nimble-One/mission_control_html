/**
 * legacy code, for reference only
 */
const joystickHandler = () => {
    let last_joystick_command = {};
    let last_joystick_command_change = Date.now();
    const joystick_status = document.getElementById("joystick-status");
    window.addEventListener("gamepadconnected", (e) => {

        const pollButtons = () => {
            requestAnimationFrame(pollButtons);
            let gamepads = navigator.getGamepads();
            let non_null_gamepads = gamepads.filter(obj => Boolean(obj))
            if (non_null_gamepads.length != 1) {
                if (non_null_gamepads.length > 1) {
                    joystick_status.className = "joystick-status-too-many";
                } else {
                    joystick_status.className = "joystick-status-disconnected";
                }
                return;
            }

            const gp = non_null_gamepads[0];

            if (gp.id.includes("Xbox")) {
                var joystick_command = {
                    LeftJoystickX: gp.axes[0],
                    LeftJoystickY: gp.axes[1],
                    RightJoystickX: gp.axes[3],
                    RightJoystickY: gp.axes[4],
                    LeftTrigger: (gp.axes[2] + 1) / 2,
                    RightTrigger: (gp.axes[5] + 1) / 2,
                    LeftDPad: gp.axes[6] < -0.5 ? 1 : 0,
                    RightDPad: gp.axes[6] > 0.5 ? 1 : 0,
                    UpDPad: gp.axes[7] < -0.5 ? 1 : 0,
                    DownDPad: gp.axes[7] > 0.5 ? 1 : 0,
                    LeftBumper: gp.buttons[4].pressed,
                    RightBumper: gp.buttons[5].pressed,
                    A: gp.buttons[0].pressed,
                    B: gp.buttons[1].pressed,
                    X: gp.buttons[2].pressed,
                    Y: gp.buttons[3].pressed,
                    LeftThumb: gp.buttons[9].pressed,
                    RightThumb: gp.buttons[10].pressed,
                    Back: gp.buttons[6].pressed,
                    Start: gp.buttons[7].pressed,

                };
            } else if (gp.id.includes("Kishi")) {
                var joystick_command = {
                    LeftJoystickX: gp.axes[0],
                    LeftJoystickY: gp.axes[1],
                    RightJoystickX: gp.axes[2],
                    RightJoystickY: gp.axes[3],
                    LeftTrigger: gp.buttons[6].value,
                    RightTrigger: gp.buttons[7].value,
                    LeftDPad: gp.buttons[14].pressed,
                    RightDPad: gp.buttons[15].pressed,
                    UpDPad: gp.buttons[12].pressed,
                    DownDPad: gp.buttons[13].pressed,
                    LeftBumper: gp.buttons[4].pressed,
                    RightBumper: gp.buttons[5].pressed,
                    A: gp.buttons[0].pressed,
                    B: gp.buttons[1].pressed,
                    X: gp.buttons[2].pressed,
                    Y: gp.buttons[3].pressed,
                    LeftThumb: gp.buttons[10].pressed,
                    RightThumb: gp.buttons[11].pressed,
                    Back: gp.buttons[8].pressed,
                    Start: gp.buttons[9].pressed,
                };
            } else {
                joystick_status.className = "joystick-status-unsupported";
                return;
            }

            // Do not spam the Python module if nothing has changed
            if (joystick_command && JSON.stringify(joystick_command) != JSON.stringify(last_joystick_command)) {

                call("write/joystick", () => { }, joystick_command);
                last_joystick_command = joystick_command;
                joystick_status.className = "joystick-status-connected";
                last_joystick_command_change = Date.now();
            }
            if (Date.now() - last_joystick_command_change > 5000) {
                joystick_status.className = "joystick-status-idle";
            }
        };

        pollButtons();
    });
};
