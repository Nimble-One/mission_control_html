
const StreamingStatus = {
    UNSUPPORTED: 0,
    ON: 1,
    OFF: 2,
}

class StreamingHandler {

    constructor(statusCallback, maxErrorCount = 100) {
        this._statusCallback = statusCallback;
        this._maxErrorCount = maxErrorCount;
        this._errorCount = 0;
        this._streamStatus = StreamingStatus.OFF;
    }

    updateImage(cameraJson) {
        let rgb_src = null;
        let depth_src = null;
        if (cameraJson != null && "cams" in cameraJson) {
            const cams = cameraJson["cams"];
            const rgb_b64 = cams["camera.color"]["b64"]
            if (rgb_b64 != "") {
                rgb_src = `data:image/jpeg;base64,${rgb_b64}`;
                this._streamStatus = StreamingStatus.ON;
                this._errorCount = 0;
            }

            const depth_b64 = cams["camera.depth"]["b64"]
            if (depth_b64 != "") {
                depth_src = `data:image/jpeg;base64,${depth_b64}`;
                this._streamStatus = StreamingStatus.ON;
                this._errorCount = 0;
            }
        }

        if(this._errorCount++ > this._maxErrorCount) {
            this._streamStatus = StreamingStatus.UNSUPPORTED;
        }

        this._statusCallback(this._streamStatus, rgb_src, depth_src);
    }
};
