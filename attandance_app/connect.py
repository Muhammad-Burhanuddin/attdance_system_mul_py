import json
import logging
import os
import sys
import threading
from pathlib import Path
from datetime import datetime
import requests
from yaml import Loader, load
from zk import ZK
from zk.exception import ZKError, ZKErrorConnection, ZKNetworkError
import django
from django.utils.timezone import make_aware
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from collections import deque

# Set the environment variable for Django settings
# Default to development settings unless the environment overrides it
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attandance_app_mul.settings.dev')
django.setup()

from attandance_app.models import AttendanceRecord

class ZkConnect:
    def __init__(self, host, port, endpoint=None, transmission=False):
        """
        Connect to a ZK Teco device and fetch real-time attendance data.

        :param host: The IP address of the ZK Teco device
        :param port: The port of the device, usually 4370
        :param endpoint: Optional API endpoint
        :param transmission: Toggle real-time data transmission, False by default
        """
        self.host = host
        self.port = port
        self.endpoint = endpoint
        self.transmission = transmission
        self.connection = None
        self.user_map = {}
        self.channel_layer = get_channel_layer()
        # Protect against duplicate real-time events (same second)
        self.recent_events = deque(maxlen=500)
        self._connect()

    def _connect(self, reconnect=False):
        """Attempt to establish a connection to the ZK Teco device."""
        try:
            zk = ZK(ip=self.host, port=self.port, verbose=True)
            self.connection = zk.connect()
            if reconnect:
                logging.debug('Reconnecting...')
            logging.info(f'Connected: {self.host}:{self.port}')
            # Notify clients about connection state
            self._send_connection_status('connected')
            # Build a user map for quick name lookup
            try:
                users = self.connection.get_users()
                self.user_map = self._build_user_map(users)
            except Exception as map_err:
                logging.warning(f'Could not build user map on connect ({self.host}): {map_err}')
        except (ZKNetworkError, ZKErrorConnection, ZKError) as error:
            logging.error(f'Connection error ({self.host}): {error}')
            self._send_connection_status('disconnected')
            raise
        except Exception as error:
            logging.error(f'Unexpected error ({self.host}): {error}')
            self._send_connection_status('disconnected')
            raise

    def _send_connection_status(self, status):
        """Send connection status to the frontend via WebSocket."""
        if self.channel_layer:
            async_to_sync(self.channel_layer.group_send)(
                "attendance_updates",
                {
                    "type": "update_connection_status",
                    "host": self.host,
                    "status": status,
                },
            )

    def send_attendance_to_api(self, employee_id, employee_name, date_time):
        """Send attendance data to external APIs if configured."""
        try:
            logging.info(
                f"Forwarding attendance: id={employee_id}, name={employee_name}, time={date_time}, device={self.host}"
            )
            # Direct MUL API call (hardcoded as requested)
            from urllib.parse import quote_plus
            eid = quote_plus(str(employee_id))
            ename = quote_plus(str(employee_name))
            dtime = quote_plus(date_time if isinstance(date_time, str) else date_time.strftime("%Y-%m-%d %H:%M:%S"))
            api_url = (
                "https://api.mul.edu.pk/attendance/api.php"
                f"?method=mark_attendance&employee_id={eid}&employee_name={ename}&date_time={dtime}"
            )
            try:
                response = requests.get(api_url, timeout=10)
                body_preview = (response.text or "").strip()
                if len(body_preview) > 500:
                    body_preview = body_preview[:500] + "..."
                logging.info(
                    f"MUL API request -> GET {api_url} | status={response.status_code} | body={body_preview}"
                )
            except Exception as e:
                logging.error(f"MUL API error: {e}")

            # Optional: Cloud ingestion endpoint
            cloud_url = os.getenv('CLOUD_EVENT_URL')
            shared = os.getenv('COLLECTOR_SHARED_SECRET')
            if cloud_url:
                payload = {
                    "employee_id": str(employee_id),
                    "employee_name": employee_name,
                    "date_time": date_time if isinstance(date_time, str) else date_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "device_ip": self.host,
                }
                data = json.dumps(payload).encode('utf-8')
                headers = {"Content-Type": "application/json"}
                if shared:
                    import hashlib, hmac
                    sig = hmac.new(shared.encode('utf-8'), data, hashlib.sha256).hexdigest()
                    headers["X-Collector-Signature"] = sig
                try:
                    r = requests.post(cloud_url, data=data, headers=headers, timeout=10)
                    body_preview = (getattr(r, 'text', '') or '').strip()
                    if len(body_preview) > 500:
                        body_preview = body_preview[:500] + "..."
                    logging.info(
                        f"Cloud ingest -> POST {cloud_url} | status={r.status_code} | body={body_preview}"
                    )
                except Exception as e:
                    logging.error(f"Cloud ingest error: {e}")
            else:
                logging.debug("CLOUD_EVENT_URL not set; skipping cloud ingest")

        except Exception as e:
            logging.error(f"Send API error: {e}")

    def fetch_attendance_logs(self):
        """Fetch all attendance logs, save them to the database, and send to API."""
        if not self.connection:
            raise ZKErrorConnection('Connection is not established!')

        try:
            logs = self.connection.get_attendance()
            users = self.connection.get_users()
            # Refresh the cached user map
            self.user_map = self._build_user_map(users)

            if logs:
                print("\nAttendance Logs:")
                print("----------------")
                for log in logs:
                    print(f"User ID: {log.user_id}, Timestamp: {log.timestamp}")
                    user_name = self.user_map.get(str(log.user_id), "Unknown") or "Unknown"

                    try:
                        naive_datetime = log.timestamp.replace(tzinfo=None)
                        aware_datetime = make_aware(naive_datetime)
                        formatted_datetime = aware_datetime.strftime("%Y-%m-%d %H:%M:%S")
                        
                        # Save to database
                        attendance_record = AttendanceRecord(
                            employee_id=log.user_id,
                            employee_name=user_name,
                            date_time=aware_datetime,
                            device_ip=self.host
                        )
                        attendance_record.save()
                        print(f"Saved attendance for User {log.user_id} at {log.timestamp}")

                        # Send to API
                        self.send_attendance_to_api(log.user_id, user_name, formatted_datetime)

                    except Exception as e:
                        logging.error(f"Error saving attendance record: {e}")

            else:
                print("No attendance logs found.")

        except Exception as error:
            logging.error(f"Error fetching attendance logs: {error}")
            raise
  
    def get_all_attendance_records_updateAPI(self):
        """Fetch all attendance records from the database and update them on the API."""
        try:
            # Fetch all records from the database
            records = AttendanceRecord.objects.all()
            formatted_records = []

            for record in records:
                formatted_records.append({
                    "employee_id": record.employee_id,
                    "employee_name": record.employee_name,
                    "date_time": record.date_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "device_ip": record.device_ip,
                })

                # Send attendance data to the API
                self.send_attendance_to_api(
                    employee_id=record.employee_id,
                    employee_name=record.employee_name,
                    date_time=record.date_time.strftime("%Y-%m-%d %H:%M:%S")
                )

            return {"records": formatted_records}

        except Exception as e:
            logging.error(f"Error fetching attendance records: {e}")
            return {"error": str(e)}

    def live_attendance(self):
        """Capture real-time attendance logs and send them to API."""
        if not self.connection:
            raise ZKErrorConnection('Connection is not established!')

        try:
            print("Listening for real-time attendance events...")
            for event in self.connection.live_capture():
                if not event:
                    continue
                try:
                    user_id = event.user_id
                    timestamp = event.timestamp
                    print(f"[REAL-TIME] User {user_id} checked in at {timestamp}")

                    naive_datetime = timestamp.replace(tzinfo=None)
                    aware_datetime = make_aware(naive_datetime)
                    # Resolve employee name, refresh map if missing
                    employee_name = self.user_map.get(str(user_id))
                    if not employee_name:
                        try:
                            users = self.connection.get_users()
                            self.user_map = self._build_user_map(users)
                            employee_name = self.user_map.get(str(user_id), "Unknown") or "Unknown"
                        except Exception:
                            employee_name = "Unknown"

                    # Build a de-duplication key (device|user|YYYY-mm-dd HH:MM:SS)
                    formatted_datetime = aware_datetime.strftime("%Y-%m-%d %H:%M:%S")
                    event_key = f"{self.host}|{user_id}|{formatted_datetime}"
                    if event_key in self.recent_events:
                        # Skip duplicates emitted by the device/lib
                        continue
                    self.recent_events.append(event_key)

                    # Save to database
                    attendance_record = AttendanceRecord(
                        employee_id=user_id,
                        employee_name=employee_name,
                        date_time=aware_datetime,
                        device_ip=self.host
                    )
                    attendance_record.save()
                    print(f"Real-time attendance saved for User {user_id} at {timestamp}")

                    # Send to API
                    self.send_attendance_to_api(user_id, employee_name, formatted_datetime)

                    # Broadcast to WebSocket clients
                    self._send_real_time_data({
                        "employee_id": user_id,
                        "employee_name": employee_name,
                        "date_time": formatted_datetime,
                        "device_ip": self.host,
                    })
                except Exception as e:
                    logging.error(f"Error saving real-time attendance: {e}")
        except Exception as error:
            logging.error(f"Real-time attendance error: {error}")
            raise

    def _build_user_map(self, users):
        """Create a lookup dict for names by both uid and user_id, normalized to str."""
        mapping = {}
        for user in users:
            try:
                name = (getattr(user, 'name', None) or getattr(user, 'username', '') or '').strip()
                if not name:
                    continue
                # Some libs expose numeric uid and string user_id
                uid = getattr(user, 'uid', None)
                user_id = getattr(user, 'user_id', None)
                if uid is not None:
                    mapping[str(uid)] = name
                if user_id is not None:
                    mapping[str(user_id)] = name
            except Exception:
                continue
        return mapping

    def _send_real_time_data(self, data):
        """Send real-time attendance data to the frontend via WebSocket."""
        if self.channel_layer:
            async_to_sync(self.channel_layer.group_send)(
                "attendance_updates",
                {
                    "type": "update_attendance_data",
                    "data": data,
                },
            )
    def disconnect(self):
        """Disconnect from the device."""
        if self.connection:
            self.connection.disconnect()
            logging.info(f'Disconnected from {self.host}')
            self._send_connection_status('disconnected')


class ParseConfig:
    @staticmethod
    def _validate(config):
        """Validate the config structure."""
        if 'devices' not in config or not isinstance(config['devices'], list):
            raise Exception('Invalid config: devices list is missing!')

        for device in config['devices']:
            if 'host' not in device or 'port' not in device:
                raise Exception('Each device must have host and port!')

    @classmethod
    def parse(cls, stream):
        """Parse a YAML file into a dictionary."""
        config = load(stream, Loader=Loader)
        cls._validate(config)
        return config


def config_logger(config):
    """Configure the logging format."""
    logging.basicConfig(
        format='%(asctime)s %(name)s %(levelname)s %(lineno)d: %(message)s',
        filename=get_log_file_name(config),
        level=logging.DEBUG
    )

def get_log_file_name(config):
    """Determine the log file name."""
    if not config:
        return 'transactions.log'
    return f"{config.get('filename')}-{datetime.now().strftime('%Y-%m-%d')}.log" \
        if config.get('split') else f"{config.get('filename')}.log"


def run_device(device):
    """Run a ZK Teco device connection in a separate thread."""
    try:
        zk = ZkConnect(host=device['host'], port=device['port'])
        
        # Start real-time attendance monitoring
        zk.live_attendance()
        
    except Exception as error:
        logging.error(f"Error with device {device['host']}: {error}")


def init():
    """Initialize and manage multiple ZK Teco device connections."""
    try:
        # Load the config
        config_path = Path(os.path.abspath(__file__)).parent / 'config.yaml'
        with open(config_path, 'r') as stream:
            config = ParseConfig.parse(stream)

        # Setup logger
        config_logger(config.get('log'))

        # Get devices
        devices = config.get('devices')

        # Run each device in a separate thread
        threads = []
        for device in devices:
            thread = threading.Thread(target=run_device, args=(device,))
            thread.start()
            threads.append(thread)

        # Wait for all threads to finish
        for thread in threads:
            thread.join()

    except Exception as error:
        logging.error(error)
        sys.exit(1)


if __name__ == "__main__":
    init()
