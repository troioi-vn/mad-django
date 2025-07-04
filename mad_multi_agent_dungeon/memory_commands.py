from .models import Memory


def remember_handler(command_entry):
    agent = command_entry.agent
    parts = command_entry.command.split(maxsplit=2)
    if len(parts) < 3:
        command_entry.output = "Usage: remember <key> <value>"
        command_entry.status = "failed"
        command_entry.save()
        return

    key = parts[1]
    value = parts[2]

    try:
        memory, created = Memory.objects.get_or_create(agent=agent, key=key)
        memory.value = value
        memory.save()
        if created:
            command_entry.output = f"Memory '{key}' created successfully."
        else:
            command_entry.output = f"Memory '{key}' updated successfully."
        command_entry.status = "completed"
    except Exception as e:
        command_entry.output = f"Error remembering memory: {e}"
        command_entry.status = "failed"
    command_entry.save()


def remember_append_handler(command_entry):
    agent = command_entry.agent
    parts = command_entry.command.split(maxsplit=2)
    if len(parts) < 3:
        command_entry.output = "Usage: remember-append <key> <text_to_append>"
        command_entry.status = "failed"
        command_entry.save()
        return

    key = parts[1]
    text_to_append = parts[2]

    try:
        memory = Memory.objects.get(agent=agent, key=key)
        memory.value += " " + text_to_append
        memory.save()
        command_entry.output = f"Memory '{key}' appended successfully."
        command_entry.status = "completed"
    except Memory.DoesNotExist:
        command_entry.output = f"Memory '{key}' not found for this agent."
        command_entry.status = "failed"
    except Exception as e:
        command_entry.output = f"Error appending to memory: {e}"
        command_entry.status = "failed"
    command_entry.save()


def forget_handler(command_entry):
    agent = command_entry.agent
    parts = command_entry.command.split(maxsplit=1)
    if len(parts) < 2:
        command_entry.output = "Usage: forget <key>"
        command_entry.status = "failed"
        command_entry.save()
        return

    key = parts[1]

    try:
        memory = Memory.objects.get(agent=agent, key=key)
        memory.delete()
        command_entry.output = f"Memory '{key}' removed successfully."
        command_entry.status = "completed"
    except Memory.DoesNotExist:
        command_entry.output = f"Memory '{key}' not found for this agent."
        command_entry.status = "failed"
    except Exception as e:
        command_entry.output = f"Error removing memory: {e}"
        command_entry.status = "failed"
    command_entry.save()


def list_handler(command_entry):
    agent = command_entry.agent
    memories = Memory.objects.filter(agent=agent).order_by("key")
    if memories.exists():
        output_lines = ["Your memories:"]
        for mem in memories:
            output_lines.append(f"  - {mem.key}: {mem.value}")
        command_entry.output = "\n".join(output_lines)
    else:
        command_entry.output = "You have no memories."
    command_entry.status = "completed"
    command_entry.save()


def load_handler(command_entry):
    agent = command_entry.agent
    parts = command_entry.command.split(maxsplit=1)
    if len(parts) < 2:
        command_entry.output = "Usage: load <key>"
        command_entry.status = "failed"
        command_entry.save()
        return

    key = parts[1]
    try:
        memory = Memory.objects.get(agent=agent, key=key)
        if memory.id not in agent.memoriesLoaded:
            agent.memoriesLoaded.append(memory.id)
            agent.save()
            command_entry.output = f"Memory '{key}' loaded successfully."
            command_entry.status = "completed"
        else:
            command_entry.output = f"Memory '{key}' is already loaded."
            command_entry.status = "completed"
    except Memory.DoesNotExist:
        command_entry.output = f"Memory '{key}' not found for this agent."
        command_entry.status = "failed"
    except Exception as e:
        command_entry.output = f"Error loading memory: {e}"
        command_entry.status = "failed"
    command_entry.save()


def unload_handler(command_entry):
    agent = command_entry.agent
    parts = command_entry.command.split(maxsplit=1)
    if len(parts) < 2:
        command_entry.output = "Usage: unload <key>"
        command_entry.status = "failed"
        command_entry.save()
        return

    key = parts[1]
    try:
        memory = Memory.objects.get(agent=agent, key=key)
        if memory.id in agent.memoriesLoaded:
            agent.memoriesLoaded.remove(memory.id)
            agent.save()
            command_entry.output = f"Memory '{key}' unloaded successfully."
            command_entry.status = "completed"
        else:
            command_entry.output = f"Memory '{key}' is not currently loaded."
            command_entry.status = "completed"
    except Memory.DoesNotExist:
        command_entry.output = f"Memory '{key}' not found for this agent."
        command_entry.status = "failed"
    except Exception as e:
        command_entry.output = f"Error unloading memory: {e}"
        command_entry.status = "failed"
    command_entry.save()
