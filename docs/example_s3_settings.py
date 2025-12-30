# Exempel på Django settings för S3-lagring av media
# Lägg till i din settings.py om du vill använda S3 för mediafiler

INSTALLED_APPS += ['storages']
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', 'receptapp-media')
AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'eu-west-1')
AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/"
