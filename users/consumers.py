import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Message, User
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth.models import AnonymousUser

class ChatConsumer(AsyncWebsocketConsumer):

    @database_sync_to_async
    def get_user_from_jwt(self):
        cookies = {}
        for header in self.scope.get('headers', []):
            if header[0] == b'cookie':
                for part in header[1].decode().split('; '):
                    if '=' in part:
                        k, v = part.split('=', 1)
                        cookies[k.strip()] = v.strip()

        print(f"🍪 COOKIES: {cookies}")

        token_key = cookies.get('jwt-auth')
        if not token_key:
            return AnonymousUser()

        try:
            token = AccessToken(token_key)
            user = User.objects.get(id=token['user_id'])
            return user
        except Exception as e:
            print(f"❌ JWT Error: {e}")
            return AnonymousUser()

    async def connect(self):

        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f"chat_group_{self.room_name}"


       
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        self.user = await self.get_user_from_jwt()
        if isinstance(self.user, AnonymousUser):
            await self.send(text_data=json.dumps({'error': 'Unauthorized'}))
            await self.close()
            return

        if str(self.user.id) not in self.room_name.split('_'):
            await self.send(text_data=json.dumps({'error': 'Forbidden'}))
            await self.close()
            return

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_content = data['message']
        recipient_id = data['recipient']

        await self.save_message(self.user.id, recipient_id, message_content)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message_content,
                'sender': str(self.user.id)
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender']
        }))

    @database_sync_to_async
    def save_message(self, sender_id, receiver_id, content):
        sender = User.objects.get(id=sender_id)
        receiver = User.objects.get(id=receiver_id)
        Message.objects.create(sender=sender, receiver=receiver, content=content)