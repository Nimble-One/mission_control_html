import json
import platform
import sys
from typing import Any, Dict

import numpy as np

import nimbleone.configuration
import nimbleone.control
import nimbleone.core
import nimbleone.web.mission_control.module
import nimbleone.os
import nimbleone.os.utils
import nimbleone.os.web
from nimbleone.logger import WARNING
from nimbleone.web.mission_control.gamepad import GamepadHandler
from nimbleone.web.mission_control.camera import CameraSlotHandler


# -----------------------------------------------------------------------------
class Web(nimbleone.os.web.Web):

    def __init__(self, module: nimbleone.os.Module, runtime: nimbleone.os.Runtime):
        self._module: nimbleone.web.mission_control.module.Module = module
        self._runtime = runtime
        self._realsense = CameraSlotHandler(module, runtime)


    def _control_stack_data(self) -> Dict[str, Any]:
        stack_data = {}
        for entry in self._module.control_stack_elements:
            if "slot" in entry:
                slot = entry["slot"]
                type_name = entry["type"]
                with nimbleone.core.read(self._runtime.slot(slot)) as r:
                    value = r.read()
                if value is None:
                    stack_data[entry["slot"]] = value
                elif isinstance(value, bool):
                    stack_data[entry["slot"]] = value
                elif isinstance(value, str):
                    stack_data[entry["slot"]] = value
                elif isinstance(value, np.ndarray):
                    stack_data[entry["slot"]] = value.tolist()
                elif hasattr(value, "dtype"):
                    stack_data[entry["slot"]] = float(value)
                else:
                    WARNING(f"Reading model of type {type_name} is currently not supported")
        return stack_data

    def request(self, path: str, post_data: Any) -> Any:

        if path == "write/hal.safety":
            old_id = np.uint32(post_data["old_operating_state_id"])
            new_id = np.uint32(post_data["new_operating_state_id"])
            with nimbleone.core.write(self._runtime.slot("hal.safety.state_change_old+new")) as w:
                w.write(old_id)
                w.write(new_id)

        elif path == "write/goal":
            x = np.float64(post_data["goal_x"])
            y = np.float64(post_data["goal_y"])
            theta = np.float64(post_data["goal_theta"])
            is_relative = post_data["goal_type"]
            if is_relative:
                goal_type = np.float64(1)
            else:
                goal_type = np.float64(0)

            with nimbleone.core.write(self._runtime.slot("robot.goal_command")) as w:
                w.write(np.array([x, y, theta, goal_type]))

        elif path == "write/controlled_q":
            self._module.set_controlled_q_ref(self._runtime, np.array(post_data["controlled_q"]))

        elif path == "write/controlled_ee_positions":
            orientation_and_frame_positions = np.array(post_data["controlled_ee_positions"])
            result, closed_loop = self._module.set_controlled_ee_positions(
                self._runtime,
                orientation_and_frame_positions[0],
                orientation_and_frame_positions[1:],
            )
            return {"result": result.name, "usable": result.usable, "closed_loop": closed_loop}

        elif path == "write/model":
            for _id, entry in post_data.items():
                if "slot" in entry:
                    value = entry["value"]
                    type_name = entry["type"]
                    if type_name == "bool":
                        with nimbleone.core.write(self._runtime.slot(entry["slot"])) as w:
                            w.write(value)
                    elif type_name == "np.float64":
                        with nimbleone.core.write(self._runtime.slot(entry["slot"])) as w:
                            if value is not None:
                                w.write(np.float64(value))
                    else:
                        WARNING(f"Writing model of type {type_name} is currently not supported")

        elif path == "write/joystick":
            return self._module.set_joystick_command(self._runtime, post_data)

        elif path == "read":
            response = {
                "running": True,
                "info": {
                    "platform": platform.node(),
                    "environment": self._module.environment(self._runtime),
                    "safety": self._module.safety,
                },
            }

            query = []
            if post_data is not None and "query" in post_data:
                query = post_data["query"]

            if "control_stack_elements" in query:
                response["control_stack_elements"] = {
                    "specification": self._module.control_stack_elements,
                    "data": self._control_stack_data(),
                }

            if "model" in query:
                response["model"] = {
                    f"control-stack-{s}": v for s, v in self._control_stack_data().items()
                }

            if "safety" in query:
                with nimbleone.core.read(
                    self._runtime.slot("hal.safety.state_change_success"),
                    self._runtime.slot("hal.safety.state"),
                ) as r:
                    success = r.of(self._runtime.slot("hal.safety.state_change_success")).read()
                    state = r.of(self._runtime.slot("hal.safety.state")).read()
                if success is not None:
                    success = int(success)
                if state is not None:
                    state = int(state)
                response["safety"] = {"success": success, "state": state}

            if "wheels" in query:
                wheel_data = self._module.get_wheel_data(self._runtime)

                with nimbleone.core.read(self._runtime.slot("robot.contacts")) as r:
                    contacts: np.ndarray = r.read()
                if contacts is not None:
                    wheel_data["contacts"] = [nimbleone.control.Contact(c).name for c in contacts]

                response["wheels"] = wheel_data

            if "velocity_command" in query:
                with nimbleone.core.read(self._runtime.slot("robot.velocity_command")) as r:
                    command: np.ndarray = r.read()
                if command is not None:
                    response["velocity_command"] = command.tolist()

            if "log" in query:
                response["log"] = self._module.get_log(self._runtime)

            if "move_base_status" in query:
                response["move_base_status"] = self._module.get_move_base_status(self._runtime)

            if "batteries" in query:
                with nimbleone.core.read(self._runtime.slot("robot.batteries")) as r:
                    batteries: np.ndarray = r.read()
                if batteries is not None:
                    response["batteries"] = batteries.tolist()

            if "motor_torque" in query:
                with nimbleone.core.read(self._runtime.slot("robot.motor_torque")) as r:
                    motor_torque: np.ndarray = r.read()
                if motor_torque is not None:
                    response["motor_torque"] = motor_torque.tolist()

            if "joint_limits" in query:
                limits = self._module.get_joint_limits().tolist()
                limits = [[str(v) if not np.isfinite(v) else v for v in pair] for pair in limits]
                response["joint_limits"] = limits

            if "controlled_q_ref" in query:
                response["controlled_q_ref"] = self._module.get_controlled_q_ref(
                    self._runtime
                ).tolist()

            if "controlled_ee_positions" in query:
                response["controlled_ee_positions"] = self._module.get_controlled_ee_positions(
                    self._runtime
                ).tolist()

            # ------------------------------------------------------------------
            if "rs_camera" in query:
                camera_query = query["rs_camera"]
                sensors = camera_query["sensors"] if "sensors" in camera_query else []
                auto_rotate = camera_query["ar"] if "ar" in camera_query else False
                quality = camera_query["q"] if "q" in camera_query else 50
                response["rs_camera"] = self._realsense.read_camera_json(sensors,
                                                                         auto_rotate,
                                                                         quality)

            # ------------------------------------------------------------------
            if "gamepad" in query:
                gamepad_json = query["gamepad"]
                if len(gamepad_json) > 0:
                    GamepadHandler.update_gamepad_slot(gamepad_json["j"],
                                                       self._runtime.slot("teleop.joystick"))
                    response["gamepad"] = {"r": "1"}

            return response

        elif path == "get_camera_jpeg":
            return ("image/jpeg", self._realsense.read_camera_img_jpeg())

        elif path == "ws/": # TODO: fix the trailing "/" issue in Webserver.py
            # websocket: parse opcodes
            ret = 1
            try:
                ws_json = json.loads(post_data)
                # --- GAMEPAD ---
                if "j" in ws_json:
                    GamepadHandler.update_gamepad_slot(ws_json["j"],
                                                       self._runtime.slot("teleop.joystick"))
                    WARNING(ws_json["j"])
                    ret = 0
            except json.JSONDecodeError as e:
                print("JSON ERR:" + str(e))
            except:
                print(sys.exc_info()[0])
            finally:
                return {
                    "r": str(ret)
                }

    def can_push(self, push) -> None:
        # ----------------------------------------------------------------------
        def ws_push_camera_rgb():
            push(self._realsense.read_camera_json())

        FPS = 24.0
        # self._runtime.scheduler.schedule(nimbleone.os.utils.FunctionRoutine(ws_push_camera_rgb), (1.0))
