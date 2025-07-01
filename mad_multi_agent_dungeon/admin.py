from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from django.utils.html import format_html
from .models import Agent, CommandQueue, PerceptionQueue, Memory, LLMQueue
from .forms import SendCommandForm


class MyAdminSite(admin.AdminSite):
    site_header = "Multi-Agent Dungeon Admin"
    site_title = "MAD Admin"
    index_title = "Welcome to the Multi-Agent Dungeon"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('send_command/', self.admin_view(self.send_command_view), name='send_command'),
            path('command_log_api/', self.admin_view(self.command_log_api), name='command_log_api'),
        ]
        return custom_urls + urls

    def send_command_view(self, request):
        if request.method == 'POST':
            form = SendCommandForm(request.POST)
            if form.is_valid():
                agent = form.cleaned_data['agent']
                command_text = form.cleaned_data['command']
                CommandQueue.objects.create(agent=agent, command=command_text)
                self.message_user(request, f"Command '{command_text}' sent to {agent.name}.")
        else:
            form = SendCommandForm()
        context = {
            'site_header': self.site_header,
            'site_title': self.site_title,
            'index_title': self.index_title,
            'form': form,
        }
        return render(request, 'admin/send_command.html', context)

    def command_log_api(self, request):
        perceptions = PerceptionQueue.objects.order_by('-date')[:20]
        log_entries = []
        for p in perceptions:
            entry = {
                'date': timezone.localtime(p.date).strftime("%Y-%m-%d %H:%M:%S"),
                'text': p.text,
                'agent_name': p.agent.name,
                'type': p.type,
            }
            if p.type == 'command' and p.command:
                entry['command_id'] = p.command.id
                entry['command_text'] = p.command.command
                entry['command_output'] = p.command.output
            log_entries.append(entry)
        return JsonResponse({'log': log_entries})


admin_site = MyAdminSite(name='myadmin')


@admin.register(Agent, site=admin_site)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'look', 'location', 'level', 'tokens', 'phase', 'is_active', 'last_command_sent', 'last_retrieved', 'view_agent_dashboard')
    list_filter = ('location', 'phase', 'last_command_sent')
    search_fields = ('name', 'look', 'description', 'location')
    readonly_fields = ('last_command_sent', 'last_retrieved')

    def view_agent_dashboard(self, obj):
        url = reverse('agent_detail', args=[obj.name])
        return format_html(f'<a href="{url}" target="_blank">View Dashboard</a>')
    view_agent_dashboard.short_description = 'Dashboard'


@admin.register(CommandQueue, site=admin_site)
class CommandQueueAdmin(admin.ModelAdmin):
    list_display = ('agent', 'command', 'status', 'date', 'output')
    list_filter = ('status', 'agent', 'date')
    search_fields = ('command', 'output')
    readonly_fields = ('date', 'output')


@admin.register(PerceptionQueue, site=admin_site)
class PerceptionQueueAdmin(admin.ModelAdmin):
    list_display = ('agent', 'source_agent', 'type', 'text', 'delivered', 'date')
    list_filter = ('type', 'agent', 'source_agent', 'delivered', 'date')
    search_fields = ('text',)
    readonly_fields = ('date',)


@admin.register(Memory, site=admin_site)
class MemoryAdmin(admin.ModelAdmin):
    list_display = ('agent', 'key', 'value')
    list_filter = ('agent',)
    search_fields = ('key', 'value')


@admin.register(LLMQueue, site=admin_site)
class LLMQueueAdmin(admin.ModelAdmin):
    list_display = ('agent', 'prompt', 'status', 'yield_value', 'date', 'response')
    list_filter = ('status', 'agent', 'date')
    search_fields = ('prompt', 'response')
    readonly_fields = ('date',)
