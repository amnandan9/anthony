"""
PythonAnywhere WSGI configuration for St. Anthony Coaching Center.

PythonAnywhere will look for a variable named `application` in this file.
Paste the contents of this file into the WSGI configuration file shown in:
  Web tab → Code section → WSGI configuration file

Replace /home/YOURUSERNAME with your actual PythonAnywhere username.
"""

import sys
import os

# ── Add project root to Python path ─────────────────────────────────────────
path = '/home/YOURUSERNAME/anthony'   # ← change YOURUSERNAME
if path not in sys.path:
    sys.path.insert(0, path)

# ── Environment variables (set once here, or use a .env file) ────────────────
os.environ['SECRET_KEY']     = 'CHANGE-ME-TO-A-LONG-RANDOM-STRING'
os.environ['DEBUG']          = 'False'
os.environ['ALLOWED_HOSTS']  = 'YOURUSERNAME.pythonanywhere.com'

# ── Point Django at our settings ─────────────────────────────────────────────
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coaching_center.settings')

# ── Load the WSGI application ────────────────────────────────────────────────
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
