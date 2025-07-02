import json
from pathlib import Path

# Load data
OBJECT_DATA = json.loads(Path('/home/edward/Desktop/mad-django/mad_multi_agent_dungeon/data/objects.json').read_text())
MAP_DATA = json.loads(Path('/home/edward/Desktop/mad-django/mad_multi_agent_dungeon/data/map.json').read_text())

def ping_handler(command_entry):
    command_entry.output = "pong"
    command_entry.status = "completed"
    command_entry.save()

from .models import Agent, ObjectInstance, PerceptionQueue # Added for look_handler and ObjectInstance, and PerceptionQueue for go_handler
from .memory_commands import memory_create_handler, memory_update_handler, memory_append_handler, memory_remove_handler, memory_list_handler, memory_load_handler, memory_unload_handler
from django.utils import timezone # Added for is_active check
from datetime import timedelta # Added for where_handler

def look_handler(command_entry):
    agent = command_entry.agent
    room_id = agent.location
    room_data = MAP_DATA['rooms'].get(room_id)

    if room_data:
        room_title = room_data.get("title", f"Room {room_id}")
        room_description = room_data.get("description", "No description available.")
        exits = room_data.get("exits", {})
        available_exits = ", ".join(exits.keys()) if exits else "none"
    else:
        room_title = f"Room {room_id}"
        room_description = "An unknown room."
        available_exits = "none"

    output_lines = [f"{room_title}", f"{room_description}"]

    # Add exits to the output
    output_lines.append(f"Exits: {available_exits}")

    # Find other active agents in the same room
    active_agents = [a.name for a in Agent.objects.filter(location=room_id).exclude(pk=agent.pk) if a.is_active()]
    if active_agents:
        agent_names = ", ".join(active_agents)
        output_lines.append(f"Other agents here: {agent_names}")

    # Find objects in the current room
    objects_in_room = ObjectInstance.objects.filter(room_id=room_id)
    if objects_in_room.exists():
        object_names = ", ".join([obj.data.get("name", obj.object_id) for obj in objects_in_room])
        output_lines.append(f"Objects here: {object_names}")

    command_entry.output = "\n".join(output_lines)
    command_entry.status = "completed"
    command_entry.save()



def go_handler(command_entry):
    agent = command_entry.agent
    parts = command_entry.command.split()
    if len(parts) < 2:
        command_entry.output = "Go where?"
        command_entry.status = "completed"
        command_entry.save()
        return

    direction = parts[1].lower()
    old_room_id = agent.location

    current_room_data = MAP_DATA['rooms'].get(old_room_id)
    if not current_room_data:
        command_entry.output = f"Error: Unknown room ID: {old_room_id}"
        command_entry.status = "failed"
        command_entry.save()
        return

    exits = current_room_data.get("exits", {})
    target_room_id = exits.get(direction)

    if target_room_id:
        # Notify agents in the old room that this agent is leaving
        for other_agent in Agent.objects.filter(location=old_room_id).exclude(pk=agent.pk):
            if other_agent.is_active():
                PerceptionQueue.objects.create(
                    agent=other_agent,
                    source_agent=agent,
                    type='none',
                    text=f'{agent.name} leaves to the {direction}.'
                )

        agent.location = target_room_id
        agent.save()

        # Notify agents in the new room that this agent has arrived
        opposite_directions = {
            "north": "south", "south": "north",
            "east": "west", "west": "east",
            "up": "down", "down": "up",
        }
        arrives_from_direction = opposite_directions.get(direction, "somewhere")

        for other_agent in Agent.objects.filter(location=target_room_id).exclude(pk=agent.pk):
            if other_agent.is_active():
                PerceptionQueue.objects.create(
                    agent=other_agent,
                    source_agent=agent,
                    type='none',
                    text=f'{agent.name} arrives from the {arrives_from_direction}.'
                )

        target_room_data = MAP_DATA['rooms'].get(target_room_id)
        if target_room_data:
            exits = target_room_data.get("exits", {})
            available_exits = ", ".join(exits.keys()) if exits else "none"
            command_entry.output = f"{target_room_data['title']}\n{target_room_data['description']}\nExits: {available_exits}"
        else:
            command_entry.output = f"Moved to unknown room: {target_room_id}"
        command_entry.status = "completed"
    else:
        available_exits = ", ".join(exits.keys()) if exits else "none"
        command_entry.output = f"You can't go {direction} from here.\nAvailable exits: {available_exits}"
        command_entry.status = "completed"

    command_entry.save()


def inventory_handler(command_entry):
    agent = command_entry.agent
    if agent.inventory:
        items_list = "\n".join([f"- {item}" for item in agent.inventory])
        command_entry.output = f"Your inventory:\n{items_list}"
    else:
        command_entry.output = "Your inventory is empty."
    command_entry.status = "completed"
    command_entry.save()

def examine_handler(command_entry):
    agent = command_entry.agent
    parts = command_entry.command.split(maxsplit=1)

    if len(parts) < 2:
        command_entry.output = "Examine what?"
        command_entry.status = "completed"
        command_entry.save()
        return

    item_name = parts[1].lower()
    current_room_id = agent.location
    current_room_data = MAP_DATA['rooms'].get(current_room_id)

    if current_room_data and "items" in current_room_data:
        for item_id, item_data in current_room_data["items"].items():
            if item_id.lower() == item_name or item_data.get("title", "").lower() == item_name:
                command_entry.output = item_data.get("description", "You see nothing special.")
                command_entry.status = "completed"
                command_entry.save()
                return

    command_entry.output = f"You don't see any '{item_name}' here."
    command_entry.status = "completed"
    command_entry.save()

def where_handler(command_entry):
    agent = command_entry.agent
    room_id = agent.location
    room_data = MAP_DATA['rooms'].get(room_id, {})
    room_title = room_data.get("title", f"Room {room_id}")

    output_lines = [f"You are in: {room_title} ({room_id})"]

    # Find other active agents in the world
    active_agents = Agent.objects.filter(last_command_sent__gte=timezone.now() - timedelta(minutes=5)).exclude(pk=agent.pk)
    if active_agents.exists():
        output_lines.append("Active agents in the world:")
        for other_agent in active_agents:
            output_lines.append(f"- {other_agent.name} ({other_agent.location})")

    command_entry.output = "\\n".join(output_lines)
    command_entry.status = "completed"
    command_entry.save()

def shout_handler(command_entry):
    parts = command_entry.command.split(maxsplit=1)
    if len(parts) < 2 or not parts[1]:
        command_entry.output = "Shout what?"
    else:
        message = parts[1]
        command_entry.output = f'You shout: "{message}"'
    command_entry.status = "completed"
    command_entry.save()

def use_handler(command_entry):
    from .models import ObjectInstance
    agent = command_entry.agent
    parts = command_entry.command.split(maxsplit=1)

    if len(parts) < 2:
        command_entry.output = "Use what?"
        command_entry.status = "completed"
        command_entry.save()
        return

    object_name = parts[1].lower()
    
    try:
        obj_instance = ObjectInstance.objects.get(
            room_id=agent.location, 
            data__name__iexact=object_name
        )
        obj = obj_instance.data
        if "use" in obj["triggers"]:
            trigger = obj["triggers"]["use"]
            if trigger["type"] == "response":
                command_entry.output = trigger["value"]
                command_entry.status = "completed"
                command_entry.save()
                return
    except ObjectInstance.DoesNotExist:
        pass

    command_entry.output = f"You don't see a {object_name} here."
    command_entry.status = "completed"
    command_entry.save()


    command_entry.status = "completed"
    command_entry.save()

def help_handler(command_entry):
    available_commands = ", ".join(sorted(COMMAND_HANDLERS.keys()))
    command_entry.output = f"Available commands: {available_commands}"
    command_entry.status = "completed"
    command_entry.save()

def meditate_handler(command_entry):
    from datetime import datetime, timedelta, timezone
    agent = command_entry.agent
    parts = command_entry.command.split()

    if len(parts) < 2:
        command_entry.output = "Meditate for how long? (e.g., meditate 10m)"
        command_entry.status = "completed"
        command_entry.save()
        return

    duration_str = parts[1]
    try:
        value = int(duration_str[:-1])
        unit = duration_str[-1].lower()
        if unit == 'm':
            delta = timedelta(minutes=value)
            unit_str = "minutes"
        elif unit == 'h':
            delta = timedelta(hours=value)
            unit_str = "hours"
        else:
            raise ValueError()
    except (ValueError, TypeError):
        command_entry.output = "Invalid duration format. Use 'm' for minutes or 'h' for hours."
        command_entry.status = "completed"
        command_entry.save()
        return

    meditation_end = datetime.now(timezone.utc) + delta
    agent.flags['meditating'] = meditation_end.isoformat()
    agent.save()

    command_entry.output = f"You begin to meditate for {value} {unit_str}."
    command_entry.status = "completed"
    command_entry.save()

def wait_handler(command_entry):
    from datetime import datetime, timedelta, timezone
    agent = command_entry.agent
    parts = command_entry.command.split()

    if len(parts) < 2:
        command_entry.output = "Wait for how long? (e.g., wait 15s, wait 5m)"
        command_entry.status = "completed"
        command_entry.save()
        return

    duration_str = parts[1]
    try:
        value = int(duration_str[:-1])
        unit = duration_str[-1].lower()
        if unit == 's':
            delta = timedelta(seconds=value)
            unit_str = "seconds"
        elif unit == 'm':
            delta = timedelta(minutes=value)
            unit_str = "minutes"
        else:
            raise ValueError()
    except (ValueError, TypeError):
        command_entry.output = "Invalid duration format. Use 's' for seconds or 'm' for minutes."
        command_entry.status = "completed"
        command_entry.save()
        return

    wait_until = datetime.now(timezone.utc) + delta
    agent.flags['waiting'] = wait_until.isoformat()
    agent.save()

    command_entry.output = f"You begin to wait for {value} {unit_str}."
    command_entry.status = "completed"
    command_entry.save()


def go_wrapper(direction):
    def handler(command_entry):
        command_entry.command = f"go {direction}"
        go_handler(command_entry)
    return handler

def score_handler(command_entry):
    agent = command_entry.agent
    output_lines = [
        f"Name: {agent.name}",
        f"Level: {agent.level}",
        f"Tokens: {agent.tokens}",
        f"Location: {agent.location}"
    ]
    command_entry.output = "\n".join(output_lines)
    command_entry.status = "completed"
    command_entry.save()

def say_handler(command_entry):
    from .models import Agent, CommandQueue
    agent = command_entry.agent
    parts = command_entry.command.split(maxsplit=1)

    if len(parts) < 2 or not parts[1]:
        command_entry.output = "Say what?"
        command_entry.status = "completed"
        command_entry.save()
        return

    message = parts[1]
    command_entry.output = f'You say: "{message}"'
    command_entry.status = "completed"
    command_entry.save()

    from .models import PerceptionQueue # Import PerceptionQueue
    # Send message to other active agents in the same room
    for other_agent in Agent.objects.filter(location=agent.location).exclude(pk=agent.pk):
        if other_agent.is_active():
            PerceptionQueue.objects.create(
                agent=other_agent,
                source_agent=agent, # The agent who said the message
                type='none', # Environmental perception
                text=f'{agent.name} says: "{message}"'
            )

def edit_profile_handler(command_entry):
    agent = command_entry.agent
    parts = command_entry.command.split(maxsplit=3) # Changed maxsplit to 3

    if len(parts) < 4: # Changed to 4 parts expected
        command_entry.output = "Usage: edit profile <field> <new_value> (e.g., edit profile look a tall, dark figure)"
        command_entry.status = "completed"
        command_entry.save()
        return

    field = parts[2].lower() # Changed index to 2
    new_value = parts[3] # Changed index to 3

    if field == 'look':
        agent.look = new_value
        command_entry.output = f"Your look has been updated to: {new_value}"
    elif field == 'description':
        agent.description = new_value
        command_entry.output = f"Your description has been updated to: {new_value}"
    else:
        command_entry.output = "Invalid field. You can only edit 'look' or 'description'."
        command_entry.status = "completed"
        command_entry.save()
        return

    agent.save()
    command_entry.status = "completed"
    command_entry.save()

COMMAND_HANDLERS = {
    "ping": ping_handler,
    "look": look_handler,
    "go": go_handler,
    "inventory": inventory_handler,
    "examine": examine_handler,
    "where": where_handler,
    "shout": shout_handler,
    "use": use_handler,
    "help": help_handler,
    "commands": help_handler,
    "meditate": meditate_handler,
    "wait": wait_handler,
    "north": go_wrapper("north"),
    "n": go_wrapper("north"),
    "south": go_wrapper("south"),
    "s": go_wrapper("south"),
    "east": go_wrapper("east"),
    "e": go_wrapper("east"),
    "west": go_wrapper("west"),
    "w": go_wrapper("west"),
    "up": go_wrapper("up"),
    "u": go_wrapper("up"),
    "down": go_wrapper("down"),
    "d": go_wrapper("down"),
    "score": score_handler,
    "say": say_handler,
    "l": look_handler,
    "memory-create": memory_create_handler,
    "memory-update": memory_update_handler,
    "memory-append": memory_append_handler,
    "memory-remove": memory_remove_handler,
    "memory-list": memory_list_handler,
    "memory-load": memory_load_handler,
    "memory-unload": memory_unload_handler,
    "edit": edit_profile_handler,
}

def handle_command(command_entry):
    from django.utils import timezone
    agent = command_entry.agent
    agent.last_command_sent = timezone.now()
    agent.save()

    handler = COMMAND_HANDLERS.get(command_entry.command.split()[0]) # Get the base command
    if handler:
        handler(command_entry)
    else:
        command_entry.output = f"Unknown command: {command_entry.command}"
        command_entry.status = "failed"
        command_entry.save()

