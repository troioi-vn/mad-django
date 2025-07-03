from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from .forms import SendCommandForm
from .models import CommandQueue, PerceptionQueue, Agent, Memory, LLMQueue
import json
import os
from django.conf import settings
from django.contrib import messages


def index(request):
    agents = Agent.objects.all()
    return render(request, "mad_multi_agent_dungeon/index.html", {"agents": agents})


def command_log_api(request):
    agent_id = request.GET.get("agent_id")
    perceptions = PerceptionQueue.objects.all()
    if agent_id:
        perceptions = perceptions.filter(agent__id=agent_id)
    perceptions = perceptions.order_by("-date")[:10]  # Get last 10 perceptions
    data = {
        "perceptions": [
            {
                "agent_name": p.agent.name,
                "source_agent_name": p.source_agent.name if p.source_agent else None,
                "type": p.type,
                "command_id": (
                    p.command.id if p.type == "command" and p.command else None
                ),
                "command_text": (
                    p.command.command if p.type == "command" and p.command else None
                ),
                "text": p.text,
                "date": p.date.isoformat(),
            }
            for p in perceptions
        ]
    }
    return JsonResponse(data)


def start_agent(request, agent_name):
    agent = get_object_or_404(Agent, name=agent_name)
    agent.is_running = True
    agent.save()
    return JsonResponse(
        {"status": "success", "agent_name": agent.name, "is_running": agent.is_running}
    )


def stop_agent(request, agent_name):
    agent = get_object_or_404(Agent, name=agent_name)
    agent.is_running = False
    agent.save()
    return JsonResponse(
        {"status": "success", "agent_name": agent.name, "is_running": agent.is_running}
    )


def reset_agent(request, agent_name):
    agent = get_object_or_404(Agent, name=agent_name)
    CommandQueue.objects.filter(agent=agent).delete()
    PerceptionQueue.objects.filter(agent=agent).delete()
    LLMQueue.objects.filter(agent=agent, status__in=["pending", "thinking"]).update(
        status="failed"
    )
    agent.perception = ""

    # Load base prompt from file
    prompt_file_path = os.path.join(settings.BASE_DIR, "prompts", f"{agent.name}.md")
    if os.path.exists(prompt_file_path):
        with open(prompt_file_path, "r") as f:
            agent.prompt = f.read()
    else:
        agent.prompt = ""

    agent.save()
    return JsonResponse(
        {"status": "success", "message": f"Agent {agent.name} has been reset."}
    )


def update_prompt(request, agent_name):
    if request.method == "POST":
        agent = get_object_or_404(Agent, name=agent_name)
        data = json.loads(request.body)
        agent.prompt = data.get("prompt", agent.prompt)
        agent.perception = data.get("perception", agent.perception)
        agent.save()
        return JsonResponse(
            {"status": "success", "message": "Prompt updated successfully."}
        )
    return JsonResponse(
        {"status": "error", "message": "Invalid request method."}, status=405
    )


def agent_detail_view(request, agent_name):
    agent = get_object_or_404(Agent, name=agent_name)
    agents = Agent.objects.all().order_by("name")
    if request.method == "POST":
        form = SendCommandForm(request.POST)
        if form.is_valid():
            command_text = form.cleaned_data["command"]
            CommandQueue.objects.create(agent=agent, command=command_text)
            messages.success(request, f"Command '{command_text}' sent to {agent.name}.")
            return redirect("agent_detail", agent_name=agent.name)
    else:
        form = SendCommandForm()

    return render(
        request,
        "mad_multi_agent_dungeon/agent_detail.html",
        {"agent": agent, "agents": agents, "form": form},
    )


def agent_detail_api(request, agent_name):
    agent = get_object_or_404(Agent, name=agent_name)

    # Load map data
    map_file_path = os.path.join(os.path.dirname(__file__), "data", "map.json")
    with open(map_file_path, "r") as f:
        map_data = json.load(f)

    room_title = map_data["rooms"].get(agent.location, {}).get("title", "Unknown Room")

    # Get last 5 commands
    commands = CommandQueue.objects.filter(agent=agent).order_by("-date")[:5]
    # Get last 5 perceptions
    perceptions = PerceptionQueue.objects.filter(agent=agent).order_by("-date")[:5]
    # Get last 10 LLM queue entries, excluding 'delivered' ones
    llm_queue_entries = (
        LLMQueue.objects.filter(agent=agent)
        .exclude(status="delivered")
        .order_by("-date")[:10]
    )
    # Get loaded memories
    loaded_memory_ids = agent.memoriesLoaded if agent.memoriesLoaded is not None else []
    loaded_memories = Memory.objects.filter(id__in=loaded_memory_ids)

    data = {
        "agent": {
            "name": agent.name,
            "phase": agent.phase,
            "is_running": agent.is_running,
            "location": agent.location,
            "room_title": room_title,
            "level": agent.level,
            "tokens": agent.tokens,
            "last_command_sent": (
                agent.last_command_sent.isoformat() if agent.last_command_sent else None
            ),
            "last_retrieved": (
                agent.last_retrieved.isoformat() if agent.last_retrieved else None
            ),
            "prompt": agent.prompt,
            "perception": agent.perception,
        },
        "loaded_memories": [{"key": m.key, "value": m.value} for m in loaded_memories],
        "commands": [
            {"command": c.command, "status": c.status, "date": c.date.isoformat()}
            for c in commands
        ],
        "perceptions": [
            {"text": p.text, "date": p.date.isoformat()} for p in perceptions
        ],
        "llm_queue": [
            {
                "id": entry.id,
                "prompt": entry.prompt,
                "status": entry.status,
                "response": entry.response,
                "date": entry.date.isoformat(),
            }
            for entry in llm_queue_entries
        ],
    }
    return JsonResponse(data)


def submit_llm_response(request, agent_name):
    if request.method == "POST":
        agent = get_object_or_404(Agent, name=agent_name)
        response_text = request.POST.get("llm_response")
        if response_text:
            LLMQueue.objects.create(
                agent=agent,
                prompt="Manual submission from agent detail page.",
                response=response_text,
                status="completed",
            )
            messages.success(request, "LLM response submitted successfully.")
        else:
            messages.error(request, "LLM response cannot be empty.")
        return redirect("agent_detail", agent_name=agent.name)
    return redirect("agent_detail", agent_name=agent_name)


def update_llm_request(request, llm_id):
    if request.method == "POST":
        try:
            llm_entry = get_object_or_404(LLMQueue, id=llm_id)
            data = json.loads(request.body)
            new_status = data.get("status")
            new_response = data.get("response")

            if new_status:
                llm_entry.status = new_status
            if new_response is not None:
                llm_entry.response = new_response
            llm_entry.save()
            return JsonResponse(
                {"status": "success", "message": "LLM Request updated successfully."}
            )
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)
    return JsonResponse(
        {"status": "error", "message": "Invalid request method."}, status=405
    )
