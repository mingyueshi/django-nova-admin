"""Local image CAPTCHA demo: escalate after two failed login submissions."""
from .captcha_settings import *  # noqa: F403

NOVA_ADMIN_CAPTCHA_POLICY = "progressive"
NOVA_ADMIN_CAPTCHA_FAILURE_LIMIT = 2
# Six characters demonstrate that neither the image nor input is limited to four.
CAPTCHA_LENGTH = 6
