import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.db.models import Count
from rest_framework_simplejwt.tokens import AccessToken
from .models import Message, User, Conversation


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"chat_group_{self.room_name}"

        self.user = await self.get_user_from_jwt()

        if not self.user or not self.user.is_authenticated:
            await self.accept()
            await self.send(text_data=json.dumps({"error": "Unauthorized"}))
            await self.close()
            return

        ids = self.room_name.split("_")
        if str(self.user.id) not in ids:
            await self.accept()
            await self.send(text_data=json.dumps({"error": "Forbidden"}))
            await self.close()
            return

        other_id = next((i for i in ids if i != str(self.user.id)), None)
        self.conversation = await self.get_or_create_conversation(self.user.id, int(other_id))

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)

        if data.get("type") == "typing":
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "typing_indicator", "sender": str(self.user.id)},
            )
            return

        message_content = data.get("message", "").strip()
        recipient_id = data.get("recipient")

        if not message_content or not recipient_id:
            return

        await self.save_message(self.user.id, recipient_id, message_content)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message_content,
                "sender": str(self.user.id),
            },
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "message": event["message"],
            "sender": event["sender"],
        }))

    async def typing_indicator(self, event):
        await self.send(text_data=json.dumps({
            "type": "typing",
            "sender": event["sender"],
        }))

    @database_sync_to_async
    def get_user_from_jwt(self):
        from urllib.parse import parse_qs
        query_string = self.scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token_key = params.get("token", [None])[0]

        if not token_key:
            return AnonymousUser()

        try:
            token = AccessToken(token_key)
            return User.objects.get(id=token["user_id"])
        except Exception as e:
            print(f"JWT Error: {e}")
            return AnonymousUser()

    @database_sync_to_async
    def get_or_create_conversation(self, user_id, other_id):
        candidates = Conversation.objects.filter(
            participants__id=user_id
        ).filter(
            participants__id=other_id
        )
        for convo in candidates:
            if convo.participants.count() == 2:
                return convo

        user = User.objects.get(id=user_id)
        other = User.objects.get(id=other_id)
        convo = Conversation.objects.create()
        convo.participants.add(user, other)
        return convo

    @database_sync_to_async
    def save_message(self, sender_id, receiver_id, content):
        sender = User.objects.get(id=sender_id)
        receiver = User.objects.get(id=receiver_id)
        msg = Message.objects.create(
            conversation=self.conversation,
            sender=sender,
            receiver=receiver,
            content=content,
        )
        self.conversation.save()
        return msg
