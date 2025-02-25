from django.urls import path
from .views import attendance_home, fetch_attendance, get_all_attendance_records, real_time_attendance

urlpatterns = [
    path('', attendance_home, name='attendance_home'),
    path('fetch_attendance/', fetch_attendance, name='fetch_attendance'),
    path('real_time_attendance/', real_time_attendance, name='real_time_attendance'),
    path("get_all_attendance_records/", get_all_attendance_records, name="get_all_attendance_records"),

]
