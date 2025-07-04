from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Agent, CommandQueue, PerceptionQueue, Memory, LLMQueue, LLMAPIKey


class MyAdminSite(admin.AdminSite):
    site_header = "Multi-Agent Dungeon Admin"
    site_title = "MAD Admin"
    index_title = "Welcome to the Multi-Agent Dungeon"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = []
        return custom_urls + urls


admin_site = MyAdminSite(name="myadmin")


@admin.register(Agent, site=admin_site)
class AgentAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "look",
        "location",
        "level",
        "tokens",
        "phase",
        "perception_limit",
        "is_active",
        "last_command_sent",
        "last_retrieved",
        "view_agent_dashboard",
    )
    list_filter = ("location", "phase", "last_command_sent")
    search_fields = ("name", "look", "description", "location")
    readonly_fields = ("last_command_sent", "last_retrieved")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "look",
                    "description",
                    "location",
                    "tokens",
                    "level",
                    "phase",
                    "perception_limit",
                    "is_running",
                    "prompt",
                    "perception",
                    "memoriesLoaded",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("last_command_sent", "last_retrieved"),
                "classes": ("collapse",),
            },
        ),
    )

    def view_agent_dashboard(self, obj):
        url = reverse("agent_detail", args=[obj.name])
        return format_html(f'<a href="{url}" target="_blank">View Dashboard</a>')

    view_agent_dashboard.short_description = "Dashboard"


@admin.register(CommandQueue, site=admin_site)
class CommandQueueAdmin(admin.ModelAdmin):
    list_display = ("agent", "command", "status", "date", "output")
    list_filter = ("status", "agent", "date")
    search_fields = ("command", "output")
    readonly_fields = ("date", "output")


@admin.register(PerceptionQueue, site=admin_site)
class PerceptionQueueAdmin(admin.ModelAdmin):
    list_display = ("agent", "source_agent", "type", "text", "delivered", "date")
    list_filter = ("type", "agent", "source_agent", "delivered", "date")
    search_fields = ("text",)
    readonly_fields = ("date",)


@admin.register(Memory, site=admin_site)
class MemoryAdmin(admin.ModelAdmin):
    list_display = ("agent", "key", "value")
    list_filter = ("agent",)
    search_fields = ("key", "value")


@admin.register(LLMQueue, site=admin_site)
class LLMQueueAdmin(admin.ModelAdmin):
    list_display = ("agent", "prompt", "status", "yield_value", "date", "response")
    list_filter = ("status", "agent", "date")
    search_fields = ("prompt", "response")
    readonly_fields = ("date",)


@admin.register(LLMAPIKey, site=admin_site)
class LLMAPIKeyAdmin(admin.ModelAdmin):
    list_display = (
        "key",
        "is_active",
        "usage_count",
        "created_at",
        "last_used",
        "description",
        "parameters",
    )
    list_filter = ("is_active",)
    search_fields = ("key", "description")
    readonly_fields = ("created_at", "last_used")
