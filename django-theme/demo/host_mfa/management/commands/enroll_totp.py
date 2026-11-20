from base64 import b32encode
from getpass import getpass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django_otp.plugins.otp_totp.models import TOTPDevice


class Command(BaseCommand):
    help = "在本机为后台账号绑定第一个验证器，输入动态码确认后才保存。"

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, username, **options):
        User = get_user_model()
        try:
            user = User.objects.get_by_natural_key(username)
        except User.DoesNotExist as exc:
            raise CommandError("账号不存在。") from exc
        if not user.is_active or not user.is_staff:
            raise CommandError("需要已启用的 staff 账号。")
        devices = TOTPDevice.objects.filter(user=user, confirmed=True)
        if devices.exists():
            raise CommandError("已有验证器。请通过恢复流程先撤销遗失的设备。")
        device = TOTPDevice(user=user, name="Authenticator")
        self.stdout.write("在验证器中手动添加此密钥（TOTP，6 位，30 秒），仅在本机查看：")
        self.stdout.write(b32encode(device.bin_key).decode("ascii").rstrip("="))
        token = getpass("输入当前动态码：").strip()
        with transaction.atomic():
            User.objects.select_for_update().get(pk=user.pk)
            if devices.exists():
                raise CommandError("已有验证器。")
            device.save()
            if not device.verify_token(token):
                raise CommandError("验证失败，未保存设备。")
        self.stdout.write("验证器已绑定，请在下一周期使用新动态码登录。")
