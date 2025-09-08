from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_datetime
import hmac
import hashlib
from .models import AttendanceRecord
from .connect import ZkConnect , ParseConfig, run_device
from pathlib import Path
import logging
import threading
import os

# Track running device connections to avoid duplicate threads per device
RUNNING_DEVICES = set()
def attendance_home(request):
    """
    Render the attendance page with a list of devices (IP and port)
    loaded from the config.yaml file.
    """
    devices = []
    try:
        # Adjust the path if needed so it points to your config.yaml file.
        config_path = Path(__file__).resolve().parent / 'config.yaml'
        with open(config_path, 'r') as stream:
            config = ParseConfig.parse(stream)
            devices = config.get('devices', [])
    except Exception as e:
        logging.error("Error loading config: %s", e)
    
    return render(request, "attendance.html", {'devices': devices})


def fetch_attendance(request):
    """
    API endpoint to fetch attendance from the selected device.
    Expects two GET parameters: ip and port.
    """
    ip = request.GET.get("ip")
    port = request.GET.get("port")
    if not ip or not port:
        return JsonResponse({"error": "IP and Port are required."}, status=400)
    
    try:
        # Connect to the device and fetch logs
        zk = ZkConnect(host=ip, port=int(port))
        zk.fetch_attendance_logs()
        zk.disconnect()

        # Fetch the latest attendance records from the database.
        records = AttendanceRecord.objects.all().order_by("-date_time")
        data = [
            {
                "employee_id": record.employee_id,
                "employee_name": record.employee_name,
                "date_time": record.date_time.strftime("%Y-%m-%d %H:%M:%S"),
                "device_ip": record.device_ip,
            }
            for record in records
        ]
        return JsonResponse({"records": data})
    except Exception as e:
        logging.error("Error fetching attendance: %s", e)
        return JsonResponse({"error": str(e)}, status=500)


def real_time_attendance(request):
    """
    Render the real-time attendance page with a list of devices (IP and port)
    loaded from the config.yaml file.
    """
    devices = []
    try:
        config_path = Path(__file__).resolve().parent / 'config.yaml'
        with open(config_path, 'r') as stream:
            config = ParseConfig.parse(stream)
            devices = config.get('devices', []) 
    except Exception as e:
        logging.error("Error loading config: %s", e)
    
    return render(request, "real_time_attendance.html", {'devices': devices})

def get_all_attendance_records(request):
    if request.method == "GET":
        try:
            zk = ZkConnect(host='192.168.12.37', port=4370)  
            response = zk.get_all_attendance_records_updateAPI()
            return JsonResponse(response, status=200)
        except Exception as e:
            logging.error(f"Error fetching attendance records: {e}")
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)


def start_device(request):
    """
    Start a live connection to a selected device (non-blocking).
    GET params: ip, port
    """
    if request.method != "GET":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    ip = request.GET.get("ip")
    port = request.GET.get("port")
    if not ip or not port:
        return JsonResponse({"error": "IP and Port are required."}, status=400)

    try:
        device_key = f"{ip}:{int(port)}"
        if device_key in RUNNING_DEVICES:
            return JsonResponse({"status": "already_running", "host": ip, "port": int(port)})

        device = {"host": ip, "port": int(port)}
        thread = threading.Thread(target=run_device, args=(device,), daemon=True)
        thread.start()
        RUNNING_DEVICES.add(device_key)
        return JsonResponse({"status": "started", "host": ip, "port": int(port)})
    except Exception as e:
        logging.error(f"Error starting device {ip}:{port} - {e}")
        return JsonResponse({"error": str(e)}, status=500)


def start_all_devices(request):
    """Start live connections for all devices in config.yaml (non-blocking)."""
    if request.method != "GET":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        config_path = Path(__file__).resolve().parent / 'config.yaml'
        with open(config_path, 'r') as stream:
            config = ParseConfig.parse(stream)
            devices = config.get('devices', [])

        started = []
        for device in devices:
            try:
                device_key = f"{device['host']}:{int(device['port'])}"
                if device_key in RUNNING_DEVICES:
                    continue
                thread = threading.Thread(target=run_device, args=(device,), daemon=True)
                thread.start()
                RUNNING_DEVICES.add(device_key)
                started.append({"host": device['host'], "port": device['port']})
            except Exception as e:
                logging.error(f"Error starting device {device}: {e}")

        return JsonResponse({"status": "started", "devices": started})
    except Exception as e:
        logging.error(f"Error starting all devices: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def ingest_attendance_event(request):
    """Secure ingestion endpoint for local collectors to post events."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        import json as _json
        payload = _json.loads(request.body.decode('utf-8'))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    required = ["employee_id", "employee_name", "date_time", "device_ip"]
    if any(k not in payload for k in required):
        return HttpResponseBadRequest("Missing required fields")

    # Simple shared secret auth (set COLLECTOR_SHARED_SECRET in env)
    shared = os.getenv('COLLECTOR_SHARED_SECRET')
    signature = request.headers.get('X-Collector-Signature')
    if shared:
        body = request.body
        expected = hmac.new(shared.encode('utf-8'), body, hashlib.sha256).hexdigest()
        if not signature or signature != expected:
            return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        # Parse and save
        dt = parse_datetime(payload["date_time"])  # expects ISO or YYYY-mm-dd HH:MM:SS
        if dt is None:
            return HttpResponseBadRequest("Invalid date_time")

        record = AttendanceRecord(
            employee_id=payload["employee_id"],
            employee_name=payload.get("employee_name", "Unknown"),
            date_time=dt,
            device_ip=payload["device_ip"],
        )
        record.save()

        # Broadcast to clients
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        async_to_sync(get_channel_layer().group_send)(
            "attendance_updates",
            {
                "type": "update_attendance_data",
                "data": {
                    "employee_id": payload["employee_id"],
                    "employee_name": payload.get("employee_name", "Unknown"),
                    "date_time": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "device_ip": payload["device_ip"],
                },
            },
        )

        return JsonResponse({"status": "ok"})
    except Exception as e:
        logging.error(f"Error ingesting event: {e}")
        return JsonResponse({"error": str(e)}, status=500)
