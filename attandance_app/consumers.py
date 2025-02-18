import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

class RealTimeAttendanceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("attendance_updates", self.channel_name)
        await self.accept()
        logging.info("WebSocket connected")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("attendance_updates", self.channel_name)
        logging.info("WebSocket disconnected")

    async def send_attendance_update(self, event):
        await self.send(text_data=json.dumps(event["data"]))
