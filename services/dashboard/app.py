import threading
import socket
import gradio as gr
import pika
from pathlib import Path
import sys


# Get current script directory
current_dir = Path(__file__).resolve().parent

# Add to sys.path
sys.path.append(str(current_dir))

from ui import ui_layout
import requests
import time
# Configuration Placeholders
VIDEO_HOST = '127.0.0.1' 
DRIVER_VIDEO_PORT = 1235
LANE_VIDEO_PORT = 1236
BUFFER_SIZE = 65536
MQ_HOST = '127.0.0.1'
MQ_QUEUE = 'safety_signals'

DRIVER_SERVICE_HEALTH_URL = "http://127.0.0.1:8000/health" # Example URL
LANE_SERVICE_HEALTH_URL = "http://127.0.0.1:8001/health"
HEARTBEAT_INTERVAL = 30
SYSTEM_HEALTH = {
    "health": True,
    "service_down": []
}

global_state = {
    "signal_logs": "Waiting for broker events...\n",
    "safety_status": "AN TOÀN",
    "system_health": "Hoạt động",
    "video_front": None,  # Will hold file path or frame data
    "video_driver": None
}

def update_ui_from_state():
    # Read from the global state and return values in the exact order
    # expected by the Gradio outputs list.
    return (
        global_state["video_front"],
        global_state["video_driver"],
        global_state["signal_logs"],
        global_state["safety_status"],
        global_state["system_health"]
    )

def heartbeat_worker(target_url, interval):
    global SYSTEM_HEALTH
    service_name = "driver-service"
    
    print(f"[*] Heartbeat worker started. Checking {service_name} every {interval}s.")
    
    while True:
        try:
            # Send GET request with a strict timeout to prevent permanent hanging
            response = requests.get(target_url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check the internal logic from your FastAPI router
                if data.get("status") == "healthy" and data.get("model_loaded") is True:
                    # Service is running fine, recover if it was previously down
                    if service_name in SYSTEM_HEALTH["service_down"]:
                        SYSTEM_HEALTH["service_down"].remove(service_name)
                else:
                    # Service is up but degraded (e.g., model failed to load)
                    if service_name not in SYSTEM_HEALTH["service_down"]:
                        SYSTEM_HEALTH["service_down"].append(service_name)
            else:
                # HTTP Error code (e.g., 500, 404)
                if service_name not in SYSTEM_HEALTH["service_down"]:
                    SYSTEM_HEALTH["service_down"].append(service_name)
                    
        except (requests.exceptions.RequestException, ValueError):
            # Network failure, connection refused, or timeout occurred
            if service_name not in SYSTEM_HEALTH["service_down"]:
                SYSTEM_HEALTH["service_down"].append(service_name)
        
        # Aggregate the final health state
        SYSTEM_HEALTH["health"] = len(SYSTEM_HEALTH["service_down"]) == 0
        
        # Block the current thread for the specified interval
        time.sleep(interval)


def video_receiver_worker(host, port, target_key):
    # Open a UDP socket to listen for incoming video frames
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.0)
    try:
        sock.bind((host, port))
    except Exception as e:
        print(f"[!] Bind failed on {host}:{port}: {e}")
        return
        
    print(f"[*] Video receiver listening on {host}:{port} for {target_key}")
    temp_file = f"temp_{target_key}.jpg"
    
    while True:
        try:
            # Block until data is received on the port
            data, addr = sock.recvfrom(BUFFER_SIZE)
            if not data:
                continue
            # Write raw JPEG byte data to a local temp file
            with open(temp_file, "wb") as f:
                f.write(data)
            # Update the Gradio dashboard state image path
            global_state[target_key] = temp_file
        except socket.timeout:
            continue
        except Exception as exc:
            print(f"[!] Error in receiver {target_key}: {exc}")
            time.sleep(0.1)

def mq_consumer_worker(host, queue_name):
    # Establish connection to the RabbitMQ broker
    connection = pika.BlockingConnection(pika.ConnectionParameters(host))
    channel = connection.channel()
    channel.queue_declare(queue=queue_name)

    def callback(ch, method, properties, body):
        # TODO: Parse incoming JSON/String and aggregate safety signals
        pass

    # Subscribe to the queue with the callback handler
    channel.basic_consume(
        queue=queue_name,
        auto_ack=True,
        on_message_callback=callback
    )
    
    print(f"[*] MQ Consumer waiting for messages in '{queue_name}'")
    # Start the blocking loop to consume messages
    channel.start_consuming()

def main():
    # Start the Video Receiver for Driver (Port 1235)
    driver_video_thread = threading.Thread(
        target=video_receiver_worker, 
        args=(VIDEO_HOST, DRIVER_VIDEO_PORT, "video_driver"),
        daemon=True
    )
    driver_video_thread.start()

    # Start the Video Receiver for Lane/Front (Port 1236)
    front_video_thread = threading.Thread(
        target=video_receiver_worker, 
        args=(VIDEO_HOST, LANE_VIDEO_PORT, "video_front"),
        daemon=True
    )
    front_video_thread.start()

    # Start the RabbitMQ Consumer as a daemon thread
    mq_thread = threading.Thread(
        target=mq_consumer_worker,
        args=(MQ_HOST, MQ_QUEUE),
        daemon=True
    )
    mq_thread.start()

    heartbeart = threading.Thread(
        target=heartbeat_worker,
        args=(DRIVER_SERVICE_HEALTH_URL, HEARTBEAT_INTERVAL),
        daemon=True
    )
    heartbeart.start()

    # Build and launch the Gradio dashboard on the main thread
    dashboard = ui_layout(update_ui_from_state)

    # Start your background threads (MQ, Video, Heartbeat) here...
    # Ensure they update global_state keys instead of touching UI components directly.
    # Example: global_state["safety_status"] = "CẢNH BÁO VA CHẠM"

    # Launch the application
    dashboard.launch(server_name="127.0.0.1", server_port=7860)

if __name__ == '__main__':
    main()