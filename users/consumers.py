import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Message, User

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.other_user_username = self.scope['url_route']['kwargs']['username']
        self.user = self.scope["user"]
        
        usernames = sorted([self.user.username, self.other_user_username])
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f"chat_group_{self.room_name}"
        user = self.scope['user']
        if user.username not in self.room_name:
        await self.close()
        return
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_content = data['message']
        receiver_username = data['receiver']

        await self.save_message(self.user.username, receiver_username, message_content)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message_content,
                'sender': self.user.username
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender']
        }))

    @database_sync_to_async
    def save_message(self, sender_username, receiver_username, content):
        sender = User.objects.get(username=sender_username)
        receiver = User.objects.get(username=receiver_username)
        Message.objects.create(sender=sender, receiver=receiver, content=content)