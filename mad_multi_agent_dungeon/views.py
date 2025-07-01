from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .forms import SendCommandForm
from .models import CommandQueue, PerceptionQueue, Agent, Memory, LLMQueue
import json

def index(request):
    agents = Agent.objects.all()
    return render(request, 'mad_multi_agent_dungeon/index.html', {'agents': agents})

def command_log_api(request):
    agent_id = request.GET.get('agent_id')
    perceptions = PerceptionQueue.objects.all()
    if agent_id:
        perceptions = perceptions.filter(agent__id=agent_id)
    perceptions = perceptions.order_by('-date')[:10] # Get last 10 perceptions
    data = {
        'perceptions': [
            {
                'agent_name': p.agent.name,
                'source_agent_name': p.source_agent.name if p.source_agent else None,
                'type': p.type,
                'command_id': p.command.id if p.type == 'command' and p.command else None,
                'command_text': p.command.command if p.type == 'command' and p.command else None,
                'text': p.text,
                'date': p.date.isoformat()
            } for p in perceptions
        ]
    }
    return JsonResponse(data)

def start_agent(request, agent_name):
    agent = get_object_or_404(Agent, name=agent_name)
    agent.is_running = True
    agent.save()
    return JsonResponse({'status': 'success', 'agent_name': agent.name, 'is_running': agent.is_running})

def stop_agent(request, agent_name):
    agent = get_object_or_404(Agent, name=agent_name)
    agent.is_running = False
    agent.save()
    return JsonResponse({'status': 'success', 'agent_name': agent.name, 'is_running': agent.is_running})

def reset_agent(request, agent_name):
    agent = get_object_or_404(Agent, name=agent_name)
    CommandQueue.objects.filter(agent=agent).delete()
    PerceptionQueue.objects.filter(agent=agent).delete()
    LLMQueue.objects.filter(agent=agent).delete()
    return JsonResponse({'status': 'success', 'message': f'Queues for agent {agent.name} have been cleared.'})

def update_prompt(request, agent_name):
    if request.method == 'POST':
        agent = get_object_or_404(Agent, name=agent_name)
        data = json.loads(request.body)
        agent.prompt = data.get('prompt', agent.prompt)
        agent.perception = data.get('perception', agent.perception)
        agent.save()
        return JsonResponse({'status': 'success', 'message': 'Prompt updated successfully.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)



def send_command_api(request):
    if request.method == 'POST':
        form = SendCommandForm(request.POST)
        if form.is_valid():
            agent = form.cleaned_data['agent']
            command_text = form.cleaned_data['command']
            command = CommandQueue.objects.create(agent=agent, command=command_text)
            return JsonResponse({'status': 'success', 'command_id': command.id})
    return JsonResponse({'status': 'error'}, status=400)

def agent_detail_view(request, agent_name):
    agent = get_object_or_404(Agent, name=agent_name)
    agents = Agent.objects.all().order_by('name')
    return render(request, 'mad_multi_agent_dungeon/agent_detail.html', {'agent': agent, 'agents': agents})

def agent_detail_api(request, agent_name):
    agent = get_object_or_404(Agent, name=agent_name)

    # Get last 5 commands
    commands = CommandQueue.objects.filter(agent=agent).order_by('-date')[:5]
    # Get last 5 perceptions
    perceptions = PerceptionQueue.objects.filter(agent=agent).order_by('-date')[:5]
    # Get last LLM queue entry
    llm_queue_entry = LLMQueue.objects.filter(agent=agent).order_by('-date').first()
    # Get loaded memories
    loaded_memories = Memory.objects.filter(id__in=agent.memoriesLoaded)

    data = {
        'agent': {
            'name': agent.name,
            'phase': agent.phase,
            'is_running': agent.is_running,
            'location': agent.location,
            'level': agent.level,
            'tokens': agent.tokens,
            'last_command_sent': agent.last_command_sent.isoformat() if agent.last_command_sent else None,
            'last_retrieved': agent.last_retrieved.isoformat() if agent.last_retrieved else None,
            'prompt': agent.prompt,
            'perception': agent.perception,
        },
        'loaded_memories': [{'key': m.key, 'value': m.value} for m in loaded_memories],
        'commands': [{'command': c.command, 'status': c.status, 'date': c.date.isoformat()} for c in commands],
        'perceptions': [{'text': p.text, 'date': p.date.isoformat()} for p in perceptions],
        'llm_queue': {
            'status': llm_queue_entry.status if llm_queue_entry else None,
            'response': llm_queue_entry.response if llm_queue_entry else None,
            'date': llm_queue_entry.date.isoformat() if llm_queue_entry else None,
        }
    }
    return JsonResponse(data)