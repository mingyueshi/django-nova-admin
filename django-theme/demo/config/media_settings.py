from .settings import *  # noqa: F403

INSTALLED_APPS = [*INSTALLED_APPS, "private_media"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "media-demo.sqlite3"}}
MEDIA_ROOT = BASE_DIR.parents[1] / ".local" / "nova-private-media"
FILE_UPLOAD_PERMISSIONS = 0o600
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o700
