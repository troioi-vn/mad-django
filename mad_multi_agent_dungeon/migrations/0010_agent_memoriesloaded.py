# Generated by Django 5.2.3 on 2025-06-30 18:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mad_multi_agent_dungeon", "0009_memory_delete_agentmemory"),
    ]

    operations = [
        migrations.AddField(
            model_name="agent",
            name="memoriesLoaded",
            field=models.JSONField(blank=True, default=list, null=True),
        ),
    ]
