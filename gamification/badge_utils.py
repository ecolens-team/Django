"""
badge awarding logic, called here: 
  - observations/signals.py(post_save on Observation)
  - gamification/views.py (SubmitObservationToQuestView when a quest completes)
"""


def _already_earned_ids(user):
    from .models import UserBadge
    return set(UserBadge.objects.filter(user=user).values_list('badge_id', flat=True))


def _try_award(user, badge, already_earned_ids):
    if badge.id in already_earned_ids:
        return False
    from .models import UserBadge
    UserBadge.objects.create(user=user, badge=badge)
    already_earned_ids.add(badge.id)
    return True


def check_badges_on_observation(user, species):
    """
    Checks two things:
    1. OBSERVATION_COUNT milestones
    2. FIRST_SPECIES 
    """
    from .models import Badge
    from observations.models import Observation

    earned = _already_earned_ids(user)

    obs_count = Observation.objects.filter(user=user).count()
    for badge in Badge.objects.filter(criteria_type=Badge.CriteriaType.OBSERVATION_COUNT):
        if obs_count >= badge.criteria_value:
            _try_award(user, badge, earned)

    if species is not None:
        other_count = (
            Observation.objects
            .filter(species=species)
            .exclude(user=user)
            .count()
        )
        if other_count == 0:
            for badge in Badge.objects.filter(criteria_type=Badge.CriteriaType.FIRST_SPECIES):
                _try_award(user, badge, earned)


def check_badges_on_quest_complete(user, quest):
    """
    Checks two things:
    1. Quest-specific badge
    2. QUEST_COUNT milestones
    """
    from .models import Badge, UserQuest

    earned = _already_earned_ids(user)

    if quest.badge_id:
        _try_award(user, quest.badge, earned)

    quest_count = UserQuest.objects.filter(user=user, completed=True).count()
    for badge in Badge.objects.filter(criteria_type=Badge.CriteriaType.QUEST_COUNT):
        if quest_count >= badge.criteria_value:
            _try_award(user, badge, earned)
