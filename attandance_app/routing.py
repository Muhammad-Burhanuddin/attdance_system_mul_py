from django.urls import re_path
from .consumers import RealTimeAttendanceConsumer

websocket_urlpatterns = [
    re_path(r"ws/real_time_attendance/$", RealTimeAttendanceConsumer.as_asgi()),
]
