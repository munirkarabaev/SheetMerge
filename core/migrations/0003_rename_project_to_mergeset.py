"""Rename Project to Mergeset."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """Rename the workspace model to Mergeset and update owner accessors."""

    dependencies = [
        ("core", "0002_project_owner"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="Project",
            new_name="Mergeset",
        ),
        migrations.AlterField(
            model_name="mergeset",
            name="owner",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="mergesets",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
