import base64
import io
import math
import time
from enum import Enum

import numpy as np
from PIL import Image

import nimbleone.core
import nimbleone.os
import nimbleone.os.utils
import nimbleone.configuration
from nimbleone.logger import WARNING


# ------------------------------------------------------------------------------
class CameraSensorKind(Enum):
    REALSENSE_RGB = "camera.color"
    REALSENSE_DEPTH = "camera.depth"
    REALSENSE_ACCEL = "camera.accel"
    REALSENSE_GYRO = "camera.gyro"


# ------------------------------------------------------------------------------
class CameraSlotHandler():
    def __init__(self,
                 module: nimbleone.os.Module,
                 runtime: nimbleone.os.Runtime):

        self._runtime = runtime
        self._frame_width = module._camera_width
        self._frame_height = module._camera_height
        self._camera_fps = module._camera_fps
        self._accel_smoothing_coeff = module._camera_smoothing
        self._smoothed_accel = np.array((0, 0, 0), dtype=np.float32)


    # --------------------------------------------------------------------------
    def read_roll_degrees(self):
        accel_raw = None

        # read raw accelerometer values
        with nimbleone.core.read(
            self._runtime.slot(CameraSensorKind.REALSENSE_ACCEL.value)
        ) as r:
            if r.progress() > 0:
                accel_raw = r.of(self._runtime.slot(CameraSensorKind.REALSENSE_ACCEL.value)).read()

        if accel_raw is not None:
            accel_raw = np.array(accel_raw, dtype=np.float32)

        # smooth
        self._smoothed_accel = self._accel_smoothing_coeff * self._smoothed_accel + (1 - self._accel_smoothing_coeff) * accel_raw

        # normalize
        normalized_accel = self._smoothed_accel / np.linalg.norm(self._smoothed_accel)

        # compute roll angle
        roll_angle = math.atan2(normalized_accel[0], math.sqrt(math.pow(normalized_accel[1], 2) + math.pow(normalized_accel[2], 2)))
        return np.degrees(roll_angle)


    # --------------------------------------------------------------------------
    def read_camera_rgb_bin(self):
        rgb_m3 = None
        with nimbleone.core.read(
            self._runtime.slot(CameraSensorKind.REALSENSE_RGB.value)
        ) as r:
            if r.progress() > 0:
                rgb_m3 = r.of(self._runtime.slot(CameraSensorKind.REALSENSE_RGB.value)).read()

        if rgb_m3 is not None:
            rgb_m3 = np.array(rgb_m3, dtype=np.uint8).reshape((self._frame_height,
                                                               self._frame_width,
                                                               3))
        return rgb_m3


    # --------------------------------------------------------------------------
    def read_camera_depth_bin(self):
        depth_m2 = None
        with nimbleone.core.read(
            self._runtime.slot(CameraSensorKind.REALSENSE_DEPTH.value)
        ) as r:
            if r.progress() > 0:
                depth_m2 = r.of(self._runtime.slot(CameraSensorKind.REALSENSE_DEPTH.value)).read()

        if depth_m2 is not None:
            depth_m2 = np.array(depth_m2, dtype=np.uint16).reshape((self._frame_height,
                                                                    self._frame_width))
            depth_m2 = (depth_m2 / np.uint16(0xff)).astype(np.uint8)
        return depth_m2


    # --------------------------------------------------------------------------
    def read_camera_img_jpeg(self, kind, auto_rotate, quality):
        jpeg = ""
        img_bin = None
        if kind == CameraSensorKind.REALSENSE_RGB.value:
            img_bin = self.read_camera_rgb_bin()
        elif kind == CameraSensorKind.REALSENSE_DEPTH.value:
            img_bin = self.read_camera_depth_bin()

        if img_bin is not None:
            image = Image.fromarray(img_bin)
            if auto_rotate:
                image = image.rotate(self.read_roll_degrees(), Image.NEAREST)

            buf = io.BytesIO()
            image.save(buf, format="JPEG", quality=quality)
            jpeg = buf.getvalue()
        return jpeg


    # --------------------------------------------------------------------------
    def read_camera_img_b64(self, kind, auto_rotate, quality):
        jpeg = self.read_camera_img_jpeg(kind, auto_rotate, quality)
        return jpeg if jpeg == "" else base64.b64encode(jpeg).decode("utf-8")


    # --------------------------------------------------------------------------
    def read_camera_json(self, sensors, auto_rotate, quality):
        cam_json = {}
        for sensor in sensors:
            b64 = self.read_camera_img_b64(sensor, auto_rotate, quality)
            cam_json[sensor] = {
                "b64": b64,
                "ts": str(time.time())
            }
        return {"cams": cam_json}
