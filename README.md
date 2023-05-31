# Mission Control

## How to test

On the web server PC (Aru's NUC or dev PC):

```bash
./launch_files/aru_v2/vivatech/nuc_mission_control_rs.yaml
# or
./launch_files/aru_v2/hardware_tests/navigation_with_pd_controller.yaml
```

On Aru's UP²:

```bash
./launch_files/aru_v2/vivatech/up2_robot_navigation_real --safety.wheels --safety.joints
```

On the client:

Open a web browser (preferably Chromium, Firefox doesn't handle the gamepad), then go to: <web_server_ip:port>/nimbleone/web/mission_control/index.html


## How does it work

The main client's code is in `index.html` file. We send a big POST request every `REQUESTS_PER_SECOND` to the server, this payload contains the gamepad's button and axis status.

The server will send back the robot's status and the vision's RealSense output image as a base64/JPEG stream.
