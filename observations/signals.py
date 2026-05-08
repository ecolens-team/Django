from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Like, Comment, Observation


@receiver(post_save, sender=Like)
def notify_like(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.user == instance.observation.user:
        return
    from users.models import Notification
    from users.signals import push_notification
    notif = Notification.objects.create(
        recipient=instance.observation.user,
        sender=instance.user,
        notif_type='like',
        content_id=instance.observation.id,
        message=f"{instance.user.username} liked your observation",
    )
    push_notification(notif)


@receiver(post_save, sender=Comment)
def notify_comment(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.user == instance.observation.user:
        return
    from users.models import Notification
    from users.signals import push_notification
    notif = Notification.objects.create(
        recipient=instance.observation.user,
        sender=instance.user,
        notif_type='comment',
        content_id=instance.observation.id,
        message=f"{instance.user.username} commented on your observation",
    )
    push_notification(notif)


@receiver(post_save, sender=Observation)
def check_observation_badges(sender, instance, created, **kwargs):
    if not created or not instance.user_id or not instance.species_id:
        return
    from gamification.badge_utils import check_badges_on_observation
    check_badges_on_observation(instance.user, instance.species)