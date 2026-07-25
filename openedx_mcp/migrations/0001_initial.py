import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MCPKey",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("key_hash", models.CharField(db_index=True, editable=False, max_length=64, unique=True)),
                ("key_prefix", models.CharField(editable=False, max_length=16)),
                ("scopes", models.JSONField(default=list)),
                ("is_revoked", models.BooleanField(default=False)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                           related_name="mcp_keys", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "MCP key", "verbose_name_plural": "MCP keys",
                     "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="MCPAuditLog",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tool", models.CharField(db_index=True, max_length=128)),
                ("scope", models.CharField(blank=True, max_length=64)),
                ("outcome", models.CharField(choices=[("dry_run", "dry_run"), ("attempt", "attempt"),
                                                      ("success", "success"), ("denied", "denied"),
                                                      ("error", "error")], db_index=True, max_length=16)),
                ("request_summary", models.JSONField(default=dict)),
                ("affected_count", models.PositiveIntegerField(default=0)),
                ("error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("key", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                          related_name="audit_logs", to="openedx_mcp.mcpkey")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                           to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "MCP audit log", "ordering": ["-created_at"]},
        ),
    ]
