class LanePipeline:
    """
    Temporary pipeline for lane-service.

    This stage does not run YOLO, DeepLabV3+, or OpenCV lane detection yet.
    The goal is to confirm that lane-service can read frames from video.
    """

    def process_frame(self, frame) -> dict:
        height, width = frame.shape[:2]

        return {
            "frame_width": width,
            "frame_height": height,
            "lane_detected": False,
            "lane_offset": None,
            "direction": "UNKNOWN",
            "message": "Pipeline placeholder. Lane detection algorithm is not running yet."
        }