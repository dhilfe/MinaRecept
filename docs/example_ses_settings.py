# Exempel på Django settings för e-post via AWS SES
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'email-smtp.eu-west-1.amazonaws.com'
EMAIL_PORT = 587
EMAIL_HOST_USER = os.environ.get('SES_USER')
EMAIL_HOST_PASSWORD = os.environ.get('SES_PASS')
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = 'noreply@receptapp.se'
