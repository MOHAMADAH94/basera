"""
Passenger / LiteSpeed WSGI entry for Namecheap cPanel (Setup Python App).

Application root should be this backend folder (where manage.py lives).
Startup file in cPanel: passenger_wsgi.py
"""

import os
import sys

# Project root = directory containing this file
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'basera_backend.settings')

# Ensure .env is visible before Django loads
_env = os.path.join(APP_ROOT, '.env')
if os.path.exists(_env):
    try:
        from dotenv import load_dotenv

        load_dotenv(_env)
    except ImportError:
        pass

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
