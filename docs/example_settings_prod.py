# Exempel på Django settings för produktion (utdrag)
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY')
DEBUG = False
ALLOWED_HOSTS = ['receptapp.se', 'api.receptapp.se']

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'receptapp'),
        'USER': os.environ.get('DB_USER', 'receptapp'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Static & media
STATIC_ROOT = BASE_DIR / 'static'
MEDIA_ROOT = BASE_DIR / 'media'
STATIC_URL = '/static/'
MEDIA_URL = '/media/'

# Email (exempel med AWS SES)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'email-smtp.eu-west-1.amazonaws.com'
EMAIL_PORT = 587
EMAIL_HOST_USER = os.environ.get('SES_USER')
EMAIL_HOST_PASSWORD = os.environ.get('SES_PASS')
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = 'noreply@receptapp.se'

# CORS
CORS_ALLOWED_ORIGINS = [
    'https://receptapp.se',
    'https://api.receptapp.se',
    # Lägg till iOS-appens domän om nativ
]

# S3 (valfritt, för media)
# INSTALLED_APPS += ['storages']
# DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
# AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
# AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
# AWS_STORAGE_BUCKET_NAME = 'receptapp-media'
# AWS_S3_REGION_NAME = 'eu-west-1'
