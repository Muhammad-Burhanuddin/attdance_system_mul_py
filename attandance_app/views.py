from django.shortcuts import render
from django.http import JsonResponse
from .models import AttendanceRecord
from .connect import ZkConnect , ParseConfig
from pathlib import Path
import logging

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
            devices = config.get('devices', [])  # Ensure 'devices' exists in config
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
