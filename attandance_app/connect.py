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

# Set the environment variable for Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_app_mul.settings')
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
        self._connect()

    def _connect(self, reconnect=False):
        """Attempt to establish a connection to the ZK Teco device."""
        try:
            zk = ZK(ip=self.host, port=self.port, verbose=True)
            self.connection = zk.connect()
            if reconnect:
                logging.debug('Reconnecting...')
            logging.info(f'Connected: {self.host}:{self.port}')
        except (ZKNetworkError, ZKErrorConnection, ZKError) as error:
            logging.error(f'Connection error ({self.host}): {error}')
            raise
        except Exception as error:
            logging.error(f'Unexpected error ({self.host}): {error}')
            raise

    def _send_connection_status(self, status):
        """Send connection status to the frontend via WebSocket."""
        if self.channel_layer:
            self.channel_layer.group_send(
                "attendance_status", 
                {
                    "type": "update_connection_status",
                    "host": self.host,
                    "status": status
                }
            )
   
    def send_attendance_to_api(self, employee_id, employee_name, date_time):
        """Send attendance data to the API and display response."""
        try:
            api_url = f"https://api.mul.edu.pk/attendance/api.php?method=mark_attendance&employee_id={employee_id}&employee_name={employee_name}&date_time={date_time}"
            response = requests.get(api_url)

            if response.status_code == 200:
                try:
                    # Try to parse JSON response
                    api_response = response.json()
                    print(f"✅ Attendance sent successfully for {employee_id} at {date_time}")
                    print(f"📌 API Response: {json.dumps(api_response, indent=4)}")
                except json.JSONDecodeError:
                    print(f"✅ Attendance sent successfully, but response is not JSON: {response.text}")
            else:
                print(f"❌ Failed to send attendance. Status: {response.status_code}")
                print(f"🔴 Response: {response.text}")

        except Exception as e:
            logging.error(f"⚠️ Error sending attendance to API: {e}")
            print(f"⚠️ Error sending attendance: {e}")
   
    def fetch_attendance_logs(self):
        """Fetch all attendance logs, save them to the database, and send to API."""
        if not self.connection:
            raise ZKErrorConnection('Connection is not established!')

        try:
            logs = self.connection.get_attendance()
            users = self.connection.get_users()  # Fetch users from the device
            user_map = {user.uid: user.name for user in users}  # Map user_id -> user_name

            if logs:
                print("\nAttendance Logs:")
                print("----------------")
                for log in logs:
                    print(f"User ID: {log.user_id}, Timestamp: {log.timestamp}")
                    user_name = user_map.get(log.user_id, "Unknown")

                    try:
                        naive_datetime = log.timestamp.replace(tzinfo=None)
                        aware_datetime = make_aware(naive_datetime)
                        
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
                        self.send_attendance_to_api(log.user_id, user_name, aware_datetime)

                    except Exception as e:
                        logging.error(f"Error saving attendance record: {e}")

            else:
                print("No attendance logs found.")

        except Exception as error:
            logging.error(f"Error fetching attendance logs: {error}")
            raise

    def live_attendance(self):
        """Capture real-time attendance logs and send them to API."""
        if not self.connection:
            raise ZKErrorConnection('Connection is not established!')

        def handle_real_time_attendance(event):
            """Process a real-time attendance event."""
            try:
                user_id = event.user_id
                timestamp = event.timestamp
                print(f"[REAL-TIME] User {user_id} checked in at {timestamp}")

                naive_datetime = timestamp.replace(tzinfo=None)
                aware_datetime = make_aware(naive_datetime)

                # Save to database
                attendance_record = AttendanceRecord(
                    employee_id=user_id,
                    employee_name="Unknown",
                    date_time=aware_datetime,
                    device_ip=self.host
                )
                attendance_record.save()
                print(f"Real-time attendance saved for User {user_id} at {timestamp}")

                # Send to API
                self.send_attendance_to_api(user_id, "Unknown", aware_datetime)

            except Exception as e:
                logging.error(f"Error saving real-time attendance: {e}")

        try:
            print("Listening for real-time attendance events...")
            self.connection.live_capture(callback=handle_real_time_attendance)
        except Exception as error:
            logging.error(f"Real-time attendance error: {error}")
            raise

    def _send_real_time_data(self, data):
        """Send real-time attendance data to the frontend via WebSocket."""
        if self.channel_layer:
            self.channel_layer.group_send(
                "attendance_data",
                {
                    "type": "update_attendance_data",
                    "data": data
                }
            )
    def disconnect(self):
        """Disconnect from the device."""
        if self.connection:
            self.connection.disconnect()
            logging.info(f'Disconnected from {self.host}')


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
