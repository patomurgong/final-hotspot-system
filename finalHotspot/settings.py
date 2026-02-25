"""
Django settings for finalHotspot project.
"""

from pathlib import Path
from decouple import config
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------- SECURITY ----------------
SECRET_KEY = config('SECRET_KEY', default='django-insecure--h99c%q12y#ja7s-f^o014))1*n18vr43j!ewj6vuui-s=#my1')
DEBUG = config('DEBUG', default=True, cast=bool)

# Get current ngrok URL from environment
NGROK_URL = config('NGROK_URL', default='https://fead-129-222-147-145.ngrok-free.app')

# ✅ UPDATED: Explicitly allowed your local IP and ngrok
ALLOWED_HOSTS = [
    '192.168.0.104', 
    '127.0.0.1', 
    'localhost', 
    '.ngrok-free.app'
]

# ✅ UPDATED: Dynamic CSRF trusted origins including your phone access
CSRF_TRUSTED_ORIGINS = [
    NGROK_URL,
    'http://127.0.0.1:8002',
    'http://localhost:8002',
    'http://192.168.0.104:8002',
]

# ---------------- APPLICATIONS ----------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'corsheaders',
    'rest_framework',

    # Local apps
    'hotspot_api',
]

# ---------------- MIDDLEWARE ----------------
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'hotspot_api.middleware.AdminSidebarMiddleware',
]

ROOT_URLCONF = 'finalHotspot.urls'

# ---------------- TEMPLATES ----------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
            os.path.join(BASE_DIR, 'hotspot_api/templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'finalHotspot.wsgi.application'

# ---------------- DATABASE (SQLite) ----------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ---------------- CACHE (Redis) ----------------
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://127.0.0.1:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# ---------------- AUTHENTICATION ----------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------- I18N ----------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# ---------------- STATIC & MEDIA ----------------
STATIC_URL = '/static/'
STATICFILES_DIRS = []
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# ---------------- DEFAULT ----------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------- CORS ----------------
CORS_ALLOWED_ORIGINS = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://127.0.0.1:8002",
    "http://localhost:8002",
    "http://192.168.0.104:8002",  # ✅ UPDATED
    NGROK_URL,
    NGROK_URL.replace('https://', 'http://'),
]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'ngrok-skip-browser-warning',
]
CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']

# ---------------- REST FRAMEWORK ----------------
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# ---------------- SESSION ----------------
SESSION_COOKIE_AGE = 60 * 60 * 2
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'

# ---------------- EMAIL ----------------
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ---------------- LOGGING ----------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'hotspot.log'),
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'mpesa': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'hotspot_api': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

# ---------------- M-PESA CONFIGURATION ----------------
MPESA_CONSUMER_KEY = 'FLpBBgtYYHPGeZtACflsAjdgvE2opccCo4m5O5YVpOAudTWQ'
MPESA_CONSUMER_SECRET = 'CwF6rFvsC43RGUEdRG38E7ciIZjKe00sJY1CKdRVyzJHAwoe0RSH1YmHDPYALd6Y'
MPESA_PASSKEY = 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919'
MPESA_BUSINESS_SHORTCODE = '174379'
MPESA_CALLBACK_URL = f'{NGROK_URL}/admin/hotspot_api/mpesa/callback/'

# ---------------- SMS Configuration ----------------
AFRICASTALKING_USERNAME = config('AFRICASTALKING_USERNAME', default='sandbox')
AFRICASTALKING_API_KEY = config('AFRICASTALKING_API_KEY', default='atsk_5e74dfeaa59346669a5c6bbae81e7504749514edde430bdd697e91644818d6d0e9256ea0')
AFRICASTALKING_SENDER_ID = config('AFRICASTALKING_SENDER_ID', default='KIREPA')

# ---------------- DEVELOPMENT HELPERS ----------------
if DEBUG:
    print(f"""
    =====================================
    🚀 KIREPANET HOTSPOT API STARTING
    =====================================
    📡 Local: http://192.168.0.104:8002
    🌐 Ngrok: {NGROK_URL}
    📞 M-Pesa Callback: {MPESA_CALLBACK_URL}
    =====================================
    """)