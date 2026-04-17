"""
WSGI config for EcoLens project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'EcoLens.settings')

application = get_wsgi_application()

# Force views import so the AI model loads in the master process when using
# gunicorn --preload, preventing each worker from reloading it on first request.
import observations.views  # noqa: E402, F401
