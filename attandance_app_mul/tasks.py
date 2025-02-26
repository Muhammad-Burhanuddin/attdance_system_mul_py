import os
import django
from celery import shared_task
import logging
from datetime import datetime
from zk import ZK
from django.utils.timezone import make_aware
from attandance_app.models import AttendanceRecord
import requests

# Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "attendance_app_mul.settings")
django.setup()

logger = logging.getLogger(__name__)

def fetch_attendance_from_device(host, port):
    """Fetch attendance logs from a ZKTeco device and save to database."""
    try:
        zk = ZK(ip=host, port=port, verbose=True)
        conn = zk.connect()
        logs = conn.get_attendance()
        users = conn.get_users()
        conn.disconnect()

        user_map = {user.uid: user.name for user in users}

        for log in logs:
            user_name = user_map.get(log.user_id, "Unknown")
            naive_datetime = log.timestamp.replace(tzinfo=None)
            aware_datetime = make_aware(naive_datetime)

            # Save to database
            record, created = AttendanceRecord.objects.get_or_create(
                employee_id=log.user_id,
                employee_name=user_name,
                date_time=aware_datetime,
                device_ip=host
            )
            if created:
                logger.info(f"Saved attendance for User {log.user_id} at {log.timestamp}")
                send_attendance_to_api(log.user_id, user_name, aware_datetime)
            else:
                logger.info(f"Attendance already exists for User {log.user_id} at {log.timestamp}")
    except Exception as e:
        logger.error(f"Error fetching attendance from {host}: {e}")


def send_attendance_to_api(employee_id, employee_name, date_time):
    """Send attendance data to an external API."""
    try:
        api_url = f"https://api.mul.edu.pk/attendance/api.php?method=mark_attendance&employee_id={employee_id}&employee_name={employee_name}&date_time={date_time.strftime('%d-%m-%Y %H:%M:%S')}"
        response = requests.get(api_url)

        if response.status_code == 200:
            logger.info(f"✅ Attendance sent successfully for {employee_id} at {date_time}")
        else:
            logger.warning(f"❌ Failed to send attendance for {employee_id}. Status: {response.status_code}")
    except Exception as e:
        logger.error(f"⚠️ Error sending attendance: {e}")


@shared_task
def fetch_attendance_task():
    """Celery task to fetch attendance from all configured devices."""
    devices = [
        {"host": "192.168.12.37", "port": 4370},
    ]
    for device in devices:
        fetch_attendance_from_device(device["host"], device["port"])
    logger.info("Attendance fetch task completed.")
