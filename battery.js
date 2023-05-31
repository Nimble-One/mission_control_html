const BatteryStatus = {
    UNSUPPORTED: 0,
    UNKNOWN: 1,
    CHARGING: 2,
    OK: 3,
    LOW: 4,
    VERY_LOW: 5
}


class RobotBatteryHandler {

}

class HostBatteryHandler {
    constructor(statusCallback, lowBatteryThreshold = 20, veryLowBatteryThreshold = 10) {

        this._statusCallback = statusCallback;
        this._lowThreshold = lowBatteryThreshold;
        this._veryLowThreshold = veryLowBatteryThreshold;
        this._level = 0;
        var self = this;
        // navigator.getBattery().then((battery) => {
        //     battery.addEventListener("chargingchange", () => {
        //         updateChargeInfo();
        //     });
        //     function updateChargeInfo() {
        //         console.log(`Battery charging? ${battery.charging ? "Yes" : "No"}`);
        //         self._statusCallback(self._level, BatteryStatus.CHARGING);
        //     }
        // });
        if(navigator && 'getBattery' in navigator) {

            navigator.getBattery().then((battery) => {

                function updateAllBatteryInfo() {
                    updateChargeInfo();
                    updateLevelInfo();
                    updateChargingInfo();
                    updateDischargingInfo();
                }
                updateAllBatteryInfo();

                battery.addEventListener("chargingchange", () => {
                    updateChargeInfo();
                });

                battery.addEventListener("levelchange", () => {
                    updateLevelInfo();
                });

                battery.addEventListener("chargingtimechange", () => {
                    updateChargingInfo();
                });

                battery.addEventListener("dischargingtimechange", () => {
                    updateDischargingInfo();
                });

                function updateChargeInfo() {
                    console.log(`Battery charging? ${battery.charging ? "Yes" : "No"}`);
                    if (battery.charging) {
                        self._statusCallback(self._level, BatteryStatus.CHARGING);
                    }
                }

                function updateLevelInfo() {
                    self._level = battery.level * 100;
                    console.log(`Battery level: ${self._level}%`);
                    let status = battery.charging ? BatteryStatus.CHARGING : (self._level < self._lowThreshold ? (self._level < self._veryLowThreshold ? BatteryStatus.VERY_LOW : BatteryStatus.OK) : BatteryStatus.OK);
                    self._statusCallback(self._level, status);
                }

                function updateChargingInfo() {
                    console.log(`Battery charging time: ${battery.chargingTime} seconds`);
                }

                function updateDischargingInfo() {
                    console.log(`Battery discharging time: ${battery.dischargingTime} seconds`);
                }
            });
        }
        else {
            self._statusCallback(0, BatteryStatus.UNSUPPORTED);
        }
    }
}
