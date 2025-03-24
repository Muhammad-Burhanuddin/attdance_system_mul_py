from django.db import models

class AttendanceRecord(models.Model):
    employee_id = models.CharField(max_length=255)
    employee_name = models.CharField(max_length=100)
    date_time = models.DateTimeField(auto_now_add=True)
    device_ip = models.GenericIPAddressField()

    def __str__(self):
        return f"{self.employee_name} ({self.employee_id}) - {self.date_time}"
