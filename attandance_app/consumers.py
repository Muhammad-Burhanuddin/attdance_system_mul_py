import json
from channels.generic.websocket import AsyncWebsocketConsumer

class RealTimeAttendanceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("attendance_updates", self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({"message": "Connected to WebSocket"}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("attendance_updates", self.channel_name)

    async def update_attendance_data(self, event):
        await self.send(text_data=json.dumps({"type": "update_attendance_data", "data": event["data"]}))

    async def update_connection_status(self, event):
        await self.send(text_data=json.dumps({
            "type": "update_connection_status",
            "host": event.get("host"),
            "status": event.get("status"),
        }))
