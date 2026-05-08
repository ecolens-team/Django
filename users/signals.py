from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def push_notification(notification):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"notif_{notification.recipient.id}",
        {
            "type": "send_notification",
            "data": {
                "id": notification.id,
                "notif_type": notification.notif_type,
                "sender": notification.sender.username,
                "sender_picture": notification.sender.profile_picture.url
                    if notification.sender.profile_picture else None,
                "message": notification.message,
                "content_id": notification.content_id,
                "is_read": False,
                "created_at": notification.created_at.isoformat(),
            }
        }
    )


@receiver(post_save, sender='users.Follow')
def notify_follow(sender, instance, created, **kwargs):
    if not created:
        return
    from .models import Notification
    notif = Notification.objects.create(
        recipient=instance.following,
        sender=instance.follower,
        notif_type='follow',
        message=f"{instance.follower.username} started following you",
    )
    push_notification(notif)


@receiver(post_save, sender='users.Message')
def notify_message(sender, instance, created, **kwargs):
    if not created:
        return
    from .models import Notification
    notif = Notification.objects.create(
        recipient=instance.receiver,
        sender=instance.sender,
        notif_type='message',
        content_id=instance.conversation.id if instance.conversation else None,
        message=f"{instance.sender.username} sent you a message",
    )
    push_notification(notif)