import threading
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from scipy.spatial.transform import Rotation

import nimbleone.configuration
import nimbleone.os
import nimbleone.pinocchio
from models.aru_v2.instances.main.geometry import AruInverseGeometry
from models.aru_v2.instances.main.geometry.orientation_inverse_geometry import (
    AruV2OrientationInverseGeometry,
)
from nimbleone.inverse_geometry import Result
from nimbleone.web.mission_control.camera import CameraSensorKind


class MoveBaseStatus(Enum):
    """
    Value between 1 and 9 can be found here :
    uint8 PENDING         = 0   # The goal has yet to be processed by the action server
    uint8 ACTIVE          = 1   # The goal is currently being processed by the action server
    uint8 PREEMPTED       = 2   # The goal received a cancel request after it started executing
                            #   and has since completed its execution (Terminal State)
    uint8 SUCCEEDED       = 3   # The goal was achieved successfully by the action server (Terminal State)
    uint8 ABORTED         = 4   # The goal was aborted during execution by the action server due
                            #    to some failure (Terminal State)
    uint8 REJECTED        = 5   # The goal was rejected by the action server without being processed,
                            #    because the goal was unattainable or invalid (Terminal State)
    uint8 PREEMPTING      = 6   # The goal received a cancel request after it started executing
                            #    and has not yet completed execution
    uint8 RECALLING       = 7   # The goal received a cancel request before it started executing,
                            #    but the action server has not yet confirmed that the goal is canceled
    uint8 RECALLED        = 8   # The goal received a cancel request before it started executing
                            #    and was successfully cancelled (Terminal State)
    uint8 LOST            = 9   # An action client can determine that a goal is LOST. This should not be
                            #    sent over the wire by an action server

    Additionally, we use 10 when move base status has no known goal : INACTIVE
    """

    PENDING = 0
    ACTIVE = 1
    PREEMPTED = 2
    SUCCEEDED = 3
    ABORTED = 4
    REJECTED = 5
    PREEMPTING = 6
    RECALLING = 7
    RECALLED = 8
    LOST = 9
    INACTIVE = 10


class Module(nimbleone.os.Module):
    def __init__(
        self,
        configuration: nimbleone.configuration.Configuration,
        slot_register: nimbleone.os.SlotRegister,
    ):
        self._robot_lock = threading.Lock()

        module_conf = configuration.get("mission_control")
        self._control_stack_elements = module_conf.get("control_stack_elements").typed(None)

        robot_conf = configuration.get("robot")
        joint_order_permutation = np.array(
            robot_conf.get("joint_order_permutation").typed(float), dtype=np.float64
        )
        self._robot = nimbleone.pinocchio.NimblePinocchioRobot.load_from_urdf_path(
            robot_conf.get("urdf").typed(Path),
            fixed_base=robot_conf.get("fixed").typed(bool),
            joint_order_permutation=joint_order_permutation,
            visuals=False,
        )
        self._joint_limits = np.array(robot_conf.get("joint_limits").typed(float))

        # TODO(Maximilian, 2022-01-02): Currently only works in closed cinematic loop
        self._closed_loop = True
        inverse_geometry = AruInverseGeometry(
            str(robot_conf.get("urdf").typed(Path)),
            self._joint_limits,
            robot_conf.get("g").typed(float),
            self._closed_loop,
        )
        self._inverse_geometry = AruV2OrientationInverseGeometry(inverse_geometry)

        self._default_q_base = np.array(robot_conf.get("default_q_base").typed(float))

        self._last_log_end = 0

        if "safety" in configuration.keys():
            self._safety = configuration.get("safety").typed(None)
        else:
            self._safety = {}

        slot_register.slot("robot.q").IN()
        slot_register.slot("robot.control.q_ref").IN()
        slot_register.slot("hal.log").IN()
        slot_register.slot("navstack.move_base_status").IN()
        # fmt: off
        slot_register.slot(
            "hal.safety.state_change_success").IN().slot(
            "hal.safety.state").IN()
        # fmt: on
        slot_register.slot("robot.velocity_command").IN()
        slot_register.slot("robot.batteries").IN()
        slot_register.slot("robot.contacts").IN()
        slot_register.slot("robot.motor_torque").IN()

        slot_register.slot("hal.log.skip").OUT()
        slot_register.slot("hal.safety.state_change_old+new").OUT()
        slot_register.slot("robot.q_mission_control").OUT()
        slot_register.slot("robot.goal_command").OUT()

        #slot_register.slot("teleop.joystick").OUT()

        # register all slots that are demanded by configuration
        for entry in self._control_stack_elements:
            if "slot" in entry:
                slot = slot_register.slot(entry["slot"]).IN()
                if entry.get("writeable", False):
                    slot.OUT()

        # RealSense
        slot_register.slot(CameraSensorKind.REALSENSE_RGB.value).IN()\
                     .slot(CameraSensorKind.REALSENSE_DEPTH.value).IN()
        slot_register.slot(CameraSensorKind.REALSENSE_ACCEL.value).IN()
        slot_register.slot(CameraSensorKind.REALSENSE_GYRO.value).IN()
        self._camera_width = configuration.get("camera.width").typed(int)
        self._camera_height = configuration.get("camera.height").typed(int)
        self._camera_fps = configuration.get("camera.fps").typed(int)
        self._camera_smoothing = configuration.get("mission_control.camera.accel_smoothing_coeff").typed(float)


    def launch(self, runtime: nimbleone.os.Runtime) -> None:
        self.set_controlled_q_ref(runtime, np.zeros(16))

    @property
    def control_stack_elements(self):
        return self._control_stack_elements

    @property
    def safety(self):
        return self._safety

    def environment(self, runtime: nimbleone.os.Runtime):
        for module in runtime.modules:
            if str(module.path).startswith("nimbleone/unified_communication"):
                return "hardware"
        return "simulation"

    def _q_to_positions(self, q: np.ndarray) -> Tuple[List[float], List[float]]:
        # because this class is used from a multi-threaded web server, we need to protect access t
        # its mutable state
        with self._robot_lock:
            self._robot.forward_kinematics(q)

            positions = []
            rotations = []
            try:
                for name in [
                    "c1_wheel_support",
                    "c2_wheel_support",
                    "c3_wheel_support",
                    "c4_wheel_support",
                ]:
                    positions.append(self._robot.get_frame_position(name).tolist())
                    rotations.append(self._robot.get_frame_rotation(name).tolist())
            except ValueError:
                positions = []
                rotations = []

            return positions, rotations

    def get_wheel_data(self, runtime: nimbleone.os.Runtime) -> Dict[str, Any]:
        with nimbleone.core.read(runtime.slot("robot.q")) as r:
            q = r.read()

        if q is None:
            return None

        q[: self._default_q_base.size] = self._default_q_base
        positions, rotations = self._q_to_positions(q)
        result = {
            "wheel_positions": positions,
            "wheel_rotations": rotations,
        }

        with nimbleone.core.read(runtime.slot("robot.control.q_ref")) as r:
            q_ref = r.read()

        if q_ref is not None:
            q_ref[: self._default_q_base.size] = self._default_q_base
            positions, rotations = self._q_to_positions(q_ref)
            result["wheel_positions_ref"] = positions
            result["wheel_rotations_ref"] = rotations

        return result

    def get_log(self, runtime: nimbleone.os.Runtime) -> List[str]:

        with nimbleone.core.read(runtime.slot("hal.log")) as r:
            start = r.read()
            end = r.read()
            log: str = r.read()

        if start is None:
            end = np.uint32(0)
        with nimbleone.core.write(runtime.slot("hal.log.skip")) as w:
            w.write(end)

        if log is None:
            return []

        lines = log.splitlines()
        if start > self._last_log_end + 1:
            lines.insert(0, f"... {start - self._last_log_end - 1} missing lines ...")

        self._last_log_end = end

        return lines

    def get_move_base_status(self, runtime: nimbleone.os.Runtime) -> str:

        with nimbleone.core.read(runtime.slot("navstack.move_base_status")) as r:
            status = r.read()

        if status is None:
            return "NONE"
        else:
            return MoveBaseStatus(status).name

    def get_joint_limits(self) -> np.ndarray:
        return self._joint_limits

    def set_controlled_q_ref(self, runtime: nimbleone.os.Runtime, q_c: np.ndarray):
        q = np.concatenate(
            [
                self._default_q_base,
                [q_c[0], q_c[1], -q_c[1], q_c[2], -q_c[2]],
                [q_c[3], q_c[4], -q_c[4], q_c[5], -q_c[5]],
                [q_c[6], q_c[7], -q_c[7], q_c[8], -q_c[8]],
                [q_c[9], q_c[10], -q_c[10], q_c[11], -q_c[11]],
                [q_c[12], 0.0],
                [q_c[13], 0.0],
                [q_c[14], 0.0],
                [q_c[15], 0.0],
            ]
        )
        with nimbleone.core.write(runtime.slot("robot.q_mission_control")) as w:
            w.write(q)

    def get_controlled_q_ref(self, runtime: nimbleone.os.Runtime) -> np.ndarray:
        with nimbleone.core.read(runtime.slot("robot.control.q_ref")) as r:
            q_ref = r.read()

        if q_ref is not None:
            return np.concatenate(
                [
                    [q_ref[7], q_ref[8], q_ref[10]],
                    [q_ref[12], q_ref[13], q_ref[15]],
                    [q_ref[17], q_ref[18], q_ref[20]],
                    [q_ref[22], q_ref[23], q_ref[25]],
                    [q_ref[27]],
                    [q_ref[29]],
                    [q_ref[31]],
                    [q_ref[33]],
                ]
            )
        else:
            return np.zeros(16)

    def set_controlled_ee_positions(
        self,
        runtime: nimbleone.os.Runtime,
        tilt_xyz: np.ndarray,
        positions: np.ndarray,
    ) -> Tuple[Result, bool]:
        orientation = Rotation.from_euler("xyz", tilt_xyz, degrees=True)
        orientation_and_frame_positions = np.zeros((6, 4))
        orientation_and_frame_positions[0] = orientation.as_quat()
        orientation_and_frame_positions[1:, :3] = positions
        with self._robot_lock:
            result, q = self._inverse_geometry.compute(orientation_and_frame_positions)

        base_rotation = orientation * Rotation.from_quat(self._default_q_base[3:])
        if result.usable:
            q = np.concatenate([self._default_q_base[:3], base_rotation.as_quat(), q])
            with nimbleone.core.write(runtime.slot("robot.q_mission_control")) as w:
                w.write(q)

        return result, self._closed_loop

    def get_controlled_ee_positions(self, runtime: nimbleone.os.Runtime) -> np.ndarray:
        with nimbleone.core.read(runtime.slot("robot.control.q_ref")) as r:
            q_ref = r.read()

        if q_ref is None:
            q_ref = self._robot.zero_q

        q_ref[:7] = self._default_q_base

        with self._robot_lock:
            self._robot.forward_kinematics(q_ref)
            positions = []
            frames = self._inverse_geometry.frames()
            for frame in frames:
                frame_position = self._robot.get_frame_position_from(frames[0], frame)
                positions.append(frame_position)
            return np.array(positions, dtype=np.float64)

    def set_joystick_command(self,
        runtime: nimbleone.os.Runtime,
        joystick_data: Any
    ) -> None:
        # Copied from teleop_joystick and tested
        joy = np.array([
            joystick_data["LeftJoystickX"],
            joystick_data["LeftJoystickY"],
            joystick_data["RightJoystickY"],
            joystick_data["RightJoystickX"],
            joystick_data["A"],
            joystick_data["B"],
            joystick_data["X"],
            joystick_data["Y"],
            joystick_data["LeftBumper"],
            joystick_data["RightBumper"],
            joystick_data["LeftTrigger"],
            joystick_data["RightTrigger"],
            joystick_data["Back"],
            joystick_data["Start"],
            joystick_data["UpDPad"],
            joystick_data["DownDPad"],
            joystick_data["LeftDPad"],
            joystick_data["RightDPad"],
            ], dtype=np.float64)

        with nimbleone.core.write(runtime.slot("teleop.joystick")) as w:
            w.write(joy)

        return None
