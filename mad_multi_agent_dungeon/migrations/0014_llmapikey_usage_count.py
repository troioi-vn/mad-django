# Generated by Django 5.2.3 on 2025-07-03 05:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mad_multi_agent_dungeon", "0013_llmapikey"),
    ]

    operations = [
        migrations.AddField(
            model_name="llmapikey",
            name="usage_count",
            field=models.IntegerField(default=0),
        ),
    ]
