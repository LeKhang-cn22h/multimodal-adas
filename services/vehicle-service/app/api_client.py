import requests
import os
import json
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("vehicle-service")

# Lấy địa chỉ của API Gateway hoặc Aggregator từ biến môi trường
GATEWAY_HOST = os.getenv("GATEWAY_HOST", "aggregator-service")
GATEWAY_PORT = os.getenv("GATEWAY_PORT", "8003")

AGGREGATOR_URL = f"http://{GATEWAY_HOST}:{GATEWAY_PORT}/event"

def get_vietnam_time_iso():
    tz = timezone(timedelta(hours=7))
    return datetime.now(tz).isoformat()

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        import numpy as np
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

def send_alert_event(risk_level, alert_msg, objects_data):
    """
    Gửi event cảnh báo tới aggregator-service khi phát hiện nguy cơ cao.
    """
    if risk_level not in ["high", "critical"]:
        return # Chỉ gửi event khi có nguy cơ cao để tránh spam
        
    alert_lvl = "DANGEROUS" if risk_level in ["high", "critical"] else "AWAKE"
    
    payload = {
        "source": "vehicle-service",
        "alert_level": alert_lvl,
        "timestamp": get_vietnam_time_iso(),
        "data": {
            "type": "ADAS_WARNING",
            "risk_level": risk_level,
            "message": alert_msg,
            "objects_count": len(objects_data),
            "objects": objects_data
        }
    }
    
    try:
        json_data = json.dumps(payload, cls=NumpyEncoder)
        response = requests.post(AGGREGATOR_URL, data=json_data, headers={'Content-Type': 'application/json'}, timeout=2.0)
        response.raise_for_status()
        logger.info(f"Đã gửi sự kiện cảnh báo thành công: {alert_msg}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Lỗi khi gửi sự kiện cảnh báo tới Aggregator: {e}")
