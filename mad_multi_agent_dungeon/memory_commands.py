from .models import Agent, Memory, CommandQueue
from django.utils import timezone

def memory_create_handler(command_entry):
    agent = command_entry.agent
    parts = command_entry.command.split(maxsplit=2)
    if len(parts) < 3:
        command_entry.output = "Usage: memory-create <key> <value>"
        command_entry.status = "failed"
        command_entry.save()
        return

    key = parts[1]
    value = parts[2]
    
    try:
        Memory.objects.create(agent=agent, key=key, value=value)
        command_entry.output = f"Memory '{key}' created successfully."
        command_entry.status = "completed"
    except Exception as e:
        command_entry.output = f"Error creating memory: {e}"
        command_entry.status = "failed"
    command_entry.save()

def memory_update_handler(command_entry):
    agent = command_entry.agent
    parts = command_entry.command.split(maxsplit=2)
    if len(parts) < 3:
        command_entry.output = "Usage: memory-update <key> <new_value>"
        command_entry.status = "failed"
        command_entry.save()
        return

    key = parts[1]
    new_value = parts[2]
    
    try:
        memory = Memory.objects.get(agent=agent, key=key)
        memory.value = new_value
        memory.save()
        command_entry.output = f"Memory '{key}' updated successfully."
        command_entry.status = "completed"
    except Memory.DoesNotExist:
        command_entry.output = f"Memory '{key}' not found for this agent."
        command_entry.status = "failed"
    except Exception as e:
        command_entry.output = f"Error updating memory: {e}"
        command_entry.status = "failed"
    command_entry.save()

def memory_append_handler(command_entry):
    agent = command_entry.agent
    parts = command_entry.command.split(maxsplit=2)
    if len(parts) < 3:
        command_entry.output = "Usage: memory-append <key> <text_to_append>"
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

def memory_remove_handler(command_entry):
    agent = command_entry.agent
    parts = command_entry.command.split(maxsplit=1)
    if len(parts) < 2:
        command_entry.output = "Usage: memory-remove <key>"
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

def memory_list_handler(command_entry):
    agent = command_entry.agent
    memories = Memory.objects.filter(agent=agent).order_by('key')
    if memories.exists():
        output_lines = ["Your memories:"]
        for mem in memories:
            output_lines.append(f"  - {mem.key}: {mem.value}")
        command_entry.output = "\n".join(output_lines)
    else:
        command_entry.output = "You have no memories."
    command_entry.status = "completed"
    command_entry.save()

def memory_load_handler(command_entry):
    agent = command_entry.agent
    parts = command_entry.command.split(maxsplit=1)
    if len(parts) < 2:
        command_entry.output = "Usage: memory-load <key>"
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

def memory_unload_handler(command_entry):
    agent = command_entry.agent
    parts = command_entry.command.split(maxsplit=1)
    if len(parts) < 2:
        command_entry.output = "Usage: memory-unload <key>"
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

