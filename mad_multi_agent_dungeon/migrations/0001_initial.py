# Generated by Django 5.2.3 on 2025-06-30 08:54

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Agent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255, unique=True)),
                ("look", models.CharField(max_length=255)),
                ("description", models.TextField()),
                ("flags", models.JSONField(blank=True, default=dict, null=True)),
                ("inventory", models.JSONField(blank=True, default=list, null=True)),
                ("tokens", models.IntegerField(default=0)),
                ("level", models.IntegerField(default=0)),
                ("location", models.CharField(default="start_room", max_length=255)),
                ("last_command_sent", models.DateTimeField(blank=True, null=True)),
                ("last_retrieved", models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="ObjectInstance",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("object_id", models.CharField(max_length=255)),
                ("room_id", models.CharField(max_length=255)),
                ("data", models.JSONField()),
            ],
        ),
        migrations.CreateModel(
            name="CommandQueue",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("command", models.CharField(max_length=1024)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processing", "Processing"),
                            ("completed", "Completed"),
                            ("delivered", "Delivered"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("date", models.DateTimeField(auto_now_add=True)),
                ("output", models.TextField(blank=True)),
                (
                    "agent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="mad_multi_agent_dungeon.agent",
                    ),
                ),
            ],
        ),
    ]
