from django.urls import path
from .views import attendance_home, fetch_attendance, real_time_attendance

urlpatterns = [
    path('', attendance_home, name='attendance_home'),
    path('fetch_attendance/', fetch_attendance, name='fetch_attendance'),
    path('real_time_attendance/', real_time_attendance, name='real_time_attendance'),
]
