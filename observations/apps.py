import sys
from django.apps import AppConfig


class ObservationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'observations'

    def ready(self):
        import observations.signals  # noqa: F401

        # Skip AI loading for management commands (migrate, collectstatic, etc.)
        is_management_cmd = (
            len(sys.argv) >= 2
            and 'manage.py' in sys.argv[0]
            and sys.argv[1] != 'runserver'
        )
        if not is_management_cmd:
            from observations.views import _load_ai
            _load_ai()
