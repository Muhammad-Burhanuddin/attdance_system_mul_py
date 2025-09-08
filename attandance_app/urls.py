from django.urls import path
from .views import attendance_home, fetch_attendance, get_all_attendance_records, real_time_attendance, start_device, start_all_devices

urlpatterns = [
    path('', attendance_home, name='attendance_home'),
    path('fetch_attendance/', fetch_attendance, name='fetch_attendance'),
    path('real_time_attendance/', real_time_attendance, name='real_time_attendance'),
    path("get_all_attendance_records/", get_all_attendance_records, name="get_all_attendance_records"),
    path('start_device/', start_device, name='start_device'),
    path('start_all_devices/', start_all_devices, name='start_all_devices'),

]
