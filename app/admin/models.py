from tortoise import fields, models


class AdminUser(models.Model):
    id = fields.BigIntField(primary_key=True)
    username = fields.CharField(max_length=50, unique=True)
    hash_password = fields.CharField(max_length=255)
    is_superuser = fields.BooleanField(default=True)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "admin_users"
