import json
import logging
from datetime import timedelta
from pathlib import Path

from django.utils import timezone

from .memory_commands import (
    remember_handler,
    remember_append_handler,
    forget_handler,
    list_handler,
    load_handler,
    unload_handler,
)
from .models import Agent, ObjectInstance, PerceptionQueue

# Load data
OBJECT_DATA = json.loads(
    Path(
        "/home/edward/Desktop/mad-django/mad_multi_agent_dungeon/data/objects.json"
    ).read_text()
)
MAP_DATA = json.loads(
    Path(
        "/home/edward/Desktop/mad-django/mad_multi_agent_dungeon/data/map.json"
    ).read_text()
)

# Configure logging
logger = logging.getLogger(__name__)


def ping_handler(command_entry):
    logger.debug(f"Executing ping for agent {command_entry.agent.name}")
    command_entry.output = "pong"
    command_entry.status = "completed"
    command_entry.save()


def look_handler(command_entry):
    agent = command_entry.agent
    logger.debug(f"Executing look for agent {agent.name} in room {agent.location}")
    room_id = agent.location
    room_data = MAP_DATA["rooms"].get(room_id)

    if room_data:
        room_title = room_data.get("title", f"Room {room_id}")
        room_description = room_data.get("description", "No description available.")
        exits = room_data.get("exits", {})
        available_exits = ", ".join(exits.keys()) if exits else "none"
    else:
        logger.warning(f"Agent {agent.name} is in an unknown room: {room_id}")
        room_title = f"Room {room_id}"
        room_description = "An unknown room."
        available_exits = "none"

    output_lines = [f"{room_title}", f"{room_description}"]
    output_lines.append(f"Exits: {available_exits}")

    active_agents = [
        a.name
        for a in Agent.objects.filter(location=room_id).exclude(pk=agent.pk)
        if a.is_active()
    ]
    if active_agents:
        output_lines.append(f"Other agents here: {', '.join(active_agents)}")

    objects_in_room = ObjectInstance.objects.filter(room_id=room_id)
    if objects_in_room.exists():
        object_names = ", ".join(
            [obj.data.get("name", obj.object_id) for obj in objects_in_room]
        )
        output_lines.append(f"Objects here: {object_names}")

    command_entry.output = "\n".join(output_lines)
    command_entry.status = "completed"
    command_entry.save()
    logger.info(f"Agent {agent.name} looked around in {room_id}.")


def go_handler(command_entry):
    agent = command_entry.agent
    parts = command_entry.command.split()
    direction = parts[1].lower() if len(parts) > 1 else None
    logger.debug(f"Executing go for agent {agent.name} towards {direction}")

    if not direction:
        command_entry.output = "Go where?"
        command_entry.status = "failed"
        command_entry.save()
        return

    old_room_id = agent.location
    current_room_data = MAP_DATA["rooms"].get(old_room_id)

    if not current_room_data:
        logger.error(f"Agent {agent.name} in invalid room {old_room_id}")
        command_entry.output = f"Error: Unknown room ID: {old_room_id}"
        command_entry.status = "failed"
        command_entry.save()
        return

    target_room_id = current_room_data.get("exits", {}).get(direction)

    if target_room_id:
        for other_agent in Agent.objects.filter(location=old_room_id).exclude(
            pk=agent.pk
        ):
            if other_agent.is_active():
                PerceptionQueue.objects.create(
                    agent=other_agent,
                    source_agent=agent,
                    type="none",
                    text=f"{agent.name} leaves to the {direction}.",
                )
                logger.debug(
                    f"Notified {other_agent.name} of {agent.name}'s departure."
                )

        agent.location = target_room_id
        agent.save()

        opposite_directions = {
            "north": "south",
            "south": "north",
            "east": "west",
            "west": "east",
            "up": "down",
            "down": "up",
        }
        arrives_from = opposite_directions.get(direction, "somewhere")

        for other_agent in Agent.objects.filter(location=target_room_id).exclude(
            pk=agent.pk
        ):
            if other_agent.is_active():
                PerceptionQueue.objects.create(
                    agent=other_agent,
                    source_agent=agent,
                    type="none",
                    text=f"{agent.name} arrives from the {arrives_from}.",
                )
                logger.debug(f"Notified {other_agent.name} of {agent.name}'s arrival.")

        target_room_data = MAP_DATA["rooms"].get(target_room_id)
        if target_room_data:
            exits = target_room_data.get("exits", {})
            available_exits = ", ".join(exits.keys()) if exits else "none"
            command_entry.output = f"{target_room_data['title']}\n{target_room_data['description']}\nExits: {available_exits}"
        else:
            command_entry.output = f"Moved to unknown room: {target_room_id}"
        command_entry.status = "completed"
        logger.info(f"Agent {agent.name} moved from {old_room_id} to {target_room_id}.")
    else:
        available_exits = ", ".join(current_room_data.get("exits", {}).keys()) or "none"
        command_entry.output = (
            f"You can't go {direction} from here.\nAvailable exits: {available_exits}"
        )
        command_entry.status = "completed"
        logger.warning(
            f"Agent {agent.name} failed to move {direction} from {old_room_id}."
        )

    command_entry.save()


def inventory_handler(command_entry):
    agent = command_entry.agent
    logger.debug(f"Executing inventory for agent {agent.name}")
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
    item_name = parts[1].lower() if len(parts) > 1 else None
    logger.debug(f"Executing examine for agent {agent.name} on item '{item_name}'")

    if not item_name:
        command_entry.output = "Examine what?"
        command_entry.status = "failed"
        command_entry.save()
        return

    current_room_id = agent.location
    current_room_data = MAP_DATA["rooms"].get(current_room_id)

    if current_room_data and "items" in current_room_data:
        for item_id, item_data in current_room_data["items"].items():
            if (
                item_id.lower() == item_name
                or item_data.get("title", "").lower() == item_name
            ):
                command_entry.output = item_data.get(
                    "description", "You see nothing special."
                )
                command_entry.status = "completed"
                command_entry.save()
                logger.info(f"Agent {agent.name} examined '{item_name}'.")
                return

    command_entry.output = f"You don't see any '{item_name}' here."
    command_entry.status = "completed"
    command_entry.save()


def where_handler(command_entry):
    agent = command_entry.agent
    logger.debug(f"Executing where for agent {agent.name}")
    room_id = agent.location
    room_data = MAP_DATA["rooms"].get(room_id, {})
    room_title = room_data.get("title", f"Room {room_id}")

    output_lines = [f"You are in: {room_title} ({room_id})"]

    active_agents = Agent.objects.filter(
        last_command_sent__gte=timezone.now() - timedelta(minutes=5)
    ).exclude(pk=agent.pk)
    if active_agents.exists():
        output_lines.append("Active agents in the world:")
        for other_agent in active_agents:
            output_lines.append(f"- {other_agent.name} ({other_agent.location})")

    command_entry.output = "\n".join(output_lines)
    command_entry.status = "completed"
    command_entry.save()


def shout_handler(command_entry):
    agent = command_entry.agent
    message = (
        command_entry.command.split(maxsplit=1)[1]
        if len(command_entry.command.split(maxsplit=1)) > 1
        else ""
    )
    logger.debug(f"Executing shout for agent {agent.name}")
    if not message:
        command_entry.output = "Shout what?"
        command_entry.status = "failed"
        command_entry.save()
        return
    else:
        command_entry.output = f'You shout: "{message}"'
        logger.info(f"Agent {agent.name} shouted: '{message}'")
    command_entry.status = "completed"
    command_entry.save()


def use_handler(command_entry):
    from .models import ObjectInstance

    agent = command_entry.agent
    parts = command_entry.command.split(maxsplit=1)
    object_name = parts[1].lower() if len(parts) > 1 else None
    logger.debug(f"Executing use for agent {agent.name} on object '{object_name}'")

    if not object_name:
        command_entry.output = "Use what?"
        command_entry.status = "failed"
        command_entry.save()
        return

    try:
        obj_instance = ObjectInstance.objects.get(
            room_id=agent.location, data__name__iexact=object_name
        )
        obj = obj_instance.data
        if "use" in obj.get("triggers", {}):
            trigger = obj["triggers"]["use"]
            if trigger.get("type") == "response":
                command_entry.output = trigger.get("value", "You use the object.")
                command_entry.status = "completed"
                command_entry.save()
                logger.info(f"Agent {agent.name} used '{object_name}'.")
                return
    except ObjectInstance.DoesNotExist:
        pass

    command_entry.output = f"You don't see a {object_name} here."
    command_entry.status = "completed"
    command_entry.save()


def help_handler(command_entry):
    logger.debug(f"Executing help for agent {command_entry.agent.name}")
    available_commands = [
        "ping", "look", "go", "inventory", "examine", "where", "shout", "use",
        "help", "meditate", "wait", "score", "say", "edit",
        "remember", "remember-append", "forget", "list", "load", "unload"
    ]
    command_entry.output = f"Available commands: {', '.join(sorted(available_commands))}"
    command_entry.status = "completed"
    command_entry.save()


def meditate_handler(command_entry):
    from datetime import datetime, timedelta, timezone

    agent = command_entry.agent
    parts = command_entry.command.split()
    duration_str = parts[1] if len(parts) > 1 else None
    logger.debug(f"Executing meditate for agent {agent.name} for '{duration_str}'")

    if not duration_str:
        command_entry.output = "Meditate for how long? (e.g., meditate 10m)"
        command_entry.status = "failed"
        command_entry.save()
        return

    try:
        value = int(duration_str[:-1])
        unit = duration_str[-1].lower()
        if unit == "m":
            delta = timedelta(minutes=value)
            unit_str = "minutes"
        elif unit == "h":
            delta = timedelta(hours=value)
            unit_str = "hours"
        else:
            raise ValueError("Invalid time unit")
    except (ValueError, TypeError):
        command_entry.output = (
            "Invalid duration format. Use 'm' for minutes or 'h' for hours."
        )
        command_entry.status = "completed"
        command_entry.save()
        return

    meditation_end = datetime.now(timezone.utc) + delta
    agent.flags["meditating"] = meditation_end.isoformat()
    agent.save()

    command_entry.output = f"You begin to meditate for {value} {unit_str}."
    command_entry.status = "completed"
    command_entry.save()
    logger.info(f"Agent {agent.name} started meditating for {value} {unit_str}.")


def wait_handler(command_entry):
    from datetime import datetime, timedelta, timezone

    agent = command_entry.agent
    parts = command_entry.command.split()
    duration_str = parts[1] if len(parts) > 1 else None
    logger.debug(f"Executing wait for agent {agent.name} for '{duration_str}'")

    if not duration_str:
        command_entry.output = "Wait for how long? (e.g., wait 15s, wait 5m)"
        command_entry.status = "failed"
        command_entry.save()
        return

    try:
        value = int(duration_str[:-1])
        unit = duration_str[-1].lower()
        if unit == "s":
            delta = timedelta(seconds=value)
            unit_str = "seconds"
        elif unit == "m":
            delta = timedelta(minutes=value)
            unit_str = "minutes"
        else:
            raise ValueError("Invalid time unit")
    except (ValueError, TypeError):
        command_entry.output = (
            "Invalid duration format. Use 's' for seconds or 'm' for minutes."
        )
        command_entry.status = "completed"
        command_entry.save()
        return

    wait_until = datetime.now(timezone.utc) + delta
    agent.flags["waiting"] = wait_until.isoformat()
    agent.save()

    command_entry.output = f"You begin to wait for {value} {unit_str}."
    command_entry.status = "completed"
    command_entry.save()
    logger.info(f"Agent {agent.name} started waiting for {value} {unit_str}.")


def go_wrapper(direction):
    def handler(command_entry):
        command_entry.command = f"go {direction}"
        go_handler(command_entry)

    return handler


def score_handler(command_entry):
    agent = command_entry.agent
    logger.debug(f"Executing score for agent {agent.name}")
    output_lines = [
        f"Name: {agent.name}",
        f"Level: {agent.level}",
        f"Tokens: {agent.tokens}",
        f"Location: {agent.location}",
    ]
    command_entry.output = "\n".join(output_lines)
    command_entry.status = "completed"
    command_entry.save()


def say_handler(command_entry):
    from .models import Agent, PerceptionQueue

    agent = command_entry.agent
    message = (
        command_entry.command.split(maxsplit=1)[1]
        if len(command_entry.command.split(maxsplit=1)) > 1
        else ""
    )
    logger.debug(f"Executing say for agent {agent.name}")

    if not message:
        command_entry.output = "Say what?"
        command_entry.status = "failed"
        command_entry.save()
        return

    command_entry.output = f'You say: "{message}"'
    command_entry.status = "completed"
    command_entry.save()
    logger.info(f"Agent {agent.name} said: '{message}'")

    for other_agent in Agent.objects.filter(location=agent.location).exclude(
        pk=agent.pk
    ):
        if other_agent.is_active():
            PerceptionQueue.objects.create(
                agent=other_agent,
                source_agent=agent,
                type="none",
                text=f'{agent.name} says: "{message}"',
            )
            logger.debug(f"Notified {other_agent.name} of {agent.name}'s message.")


def edit_profile_handler(command_entry):
    agent = command_entry.agent
    parts = command_entry.command.split(maxsplit=3)
    logger.debug(f"Executing edit profile for agent {agent.name}")

    if len(parts) < 4:
        command_entry.output = "Usage: edit profile <field> <new_value> (e.g., edit profile look a tall, dark figure)"
        command_entry.status = "failed"
        command_entry.save()
        return

    field = parts[2].lower()
    new_value = parts[3]

    if field in ["look", "description"]:
        setattr(agent, field, new_value)
        agent.save()
        command_entry.output = f"Your {field} has been updated to: {new_value}"
        command_entry.status = "completed"
        logger.info(f"Agent {agent.name} updated their {field}.")
    else:
        command_entry.output = (
            "Invalid field. You can only edit 'look' or 'description'."
        )
        command_entry.status = "completed"
        logger.warning(
            f"Agent {agent.name} failed to update invalid profile field '{field}'."
        )

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
    "l": look_handler,
    "remember": remember_handler,
    "remember-append": remember_append_handler,
    "forget": forget_handler,
    "list": list_handler,
    "load": load_handler,
    "unload": unload_handler,
    "edit": edit_profile_handler,
}


def handle_command(command_entry):
    from django.utils import timezone

    agent = command_entry.agent
    agent.last_command_sent = timezone.now()
    agent.save()

    command_parts = command_entry.command.split()
    base_command = command_parts[0] if command_parts else ""
    handler = COMMAND_HANDLERS.get(base_command)

    logger.info(f"Handling command '{command_entry.command}' for agent {agent.name}")

    if handler:
        try:
            handler(command_entry)
            logger.info(f"Successfully handled '{base_command}' for agent {agent.name}")
        except Exception as e:
            logger.exception(
                f"Error executing handler for command '{base_command}' for agent {agent.name}"
            )
            command_entry.output = f"An error occurred: {e}"
            command_entry.status = "failed"
            command_entry.save()
    else:
        logger.warning(f"No handler found for command '{base_command}'")
        command_entry.output = f"Unknown command: {command_entry.command}"
        command_entry.status = "failed"
        command_entry.save()
