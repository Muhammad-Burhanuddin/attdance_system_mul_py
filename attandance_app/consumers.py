import json
from channels.generic.websocket import AsyncWebsocketConsumer

class RealTimeAttendanceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("attendance_updates", self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({"message": "Connected to WebSocket"}))  # Debugging

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("attendance_updates", self.channel_name)

    async def send_attendance_update(self, event):
        await self.send(text_data=json.dumps({"type": "update_attendance_data", "data": event["data"]}))
