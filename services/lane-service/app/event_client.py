import httpx

class EventClient:
    """
    Gửi cảnh báo chệch làn đường tự động đến aggregator-service.
    """
    def __init__(self, target_url: str = "http://aggregator-service:8003/event"):
        self.target_url = target_url
        # Sử dụng timeout ngắn (1 giây) để không làm chậm luồng xử lý chính
        self.client = httpx.Client(timeout=1.0)

    def send_departure_warning(self, lane_offset: float, direction: str) -> bool:
        """
        Gửi sự kiện chệch làn đường sang aggregator-service.
        """
        if direction not in ["LEFT", "RIGHT"]:
            return False
            
        payload = {
            "source": "lane-service",
            "alert_level": "WARNING",
            "lane_offset": lane_offset,
            "data": {
                "direction": direction.lower(),
                "message": f"Cảnh báo chệch làn: Xe đang bị lệch về bên {direction.lower()} ({lane_offset}m)"
            }
        }
        
        try:
            r = self.client.post(self.target_url, json=payload)
            return r.status_code == 200
        except Exception as e:
            # Log lỗi nhẹ nhàng, bỏ qua nếu aggregator-service chưa khởi động
            print(f"[EventClient] Gửi cảnh báo thất bại (Aggregator offline): {e}")
            return False

    def close(self):
        try:
            self.client.close()
        except Exception:
            pass
