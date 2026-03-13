from rest_framework.permissions import BasePermission


class IsApprovedResearcher(BasePermission):
    message = "User Doesn't have an approved Researcher account."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.role != "RESEARCHER":
            return False
        profile = getattr(user, "researcher_profile", None)
        if not profile:
            return False
        return profile.application_status == "APPROVED"
