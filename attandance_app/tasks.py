# tasks.py (inside your Django app)
from celery import shared_task
from datetime import timedelta
from django.utils import timezone
from .models import AttendanceRecord
from .connect import ZkConnect

@shared_task
def fetch_attendance_from_devices():
    """
    Fetches attendance from all configured devices every minute
    and updates the database.
    """
    from pathlib import Path
    from .connect import ParseConfig

    config_path = Path(__file__).resolve().parent / 'config.yaml'
    try:
        with open(config_path, 'r') as stream:
            config = ParseConfig.parse(stream)
            devices = config.get('devices', [])
        
        for device in devices:
            ip = device.get("host")
            port = device.get("port")

            if not ip or not port:
                continue  # Skip invalid devices
            
            try:
                zk = ZkConnect(host=ip, port=int(port))
                zk.fetch_attendance_logs()
                zk.disconnect()
            except Exception as e:
                print(f"Error fetching from {ip}: {e}")

        # Clean records older than 5 minutes
        five_minutes_ago = timezone.now() - timedelta(minutes=5)
        AttendanceRecord.objects.filter(date_time__lt=five_minutes_ago).delete()

        return "Attendance fetched successfully"
    
    except Exception as e:
        return f"Error: {e}"
