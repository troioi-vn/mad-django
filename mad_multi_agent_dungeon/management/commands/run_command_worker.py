import logging
import time
from datetime import timedelta, datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from mad_multi_agent_dungeon.models import CommandQueue, PerceptionQueue, Agent
from mad_multi_agent_dungeon.commands import handle_command

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Runs the command queue worker."

    def _process_single_command(self, command_entry):
        logger.info(
            f"Processing command: {command_entry.command} for agent {command_entry.agent.name}"
        )
        command_entry.status = "processing"
        command_entry.save()

        # Update the last_command_sent for the agent
        agent = command_entry.agent
        agent.last_command_sent = timezone.now()

        # Handle agent waiting state
        if "waiting" in agent.flags and agent.flags["waiting"]:
            wait_until_str = agent.flags["waiting"]
            wait_until = datetime.fromisoformat(wait_until_str)
            if timezone.now() < wait_until:
                logger.info(
                    f"Agent {agent.name} is waiting. Command {command_entry.command} deferred."
                )
                command_entry.status = "pending"  # Keep it pending for next iteration
                command_entry.save()
                agent.save()
                return  # Skip processing this command for now
            else:
                # Waiting period is over, clear the flag
                del agent.flags["waiting"]

        agent.save()

        try:
            handle_command(command_entry)
            command_entry.refresh_from_db()  # Reload the command_entry to get the latest output and status

            # Create a PerceptionQueue entry for the commanding agent
            PerceptionQueue.objects.create(
                agent=command_entry.agent,
                source_agent=command_entry.agent,
                type="command",
                command=command_entry,
                text=f"MAD: [command|{command_entry.command}].\n{command_entry.output}",
            )

            # Handle "shout" command for other active agents in the same room
            if command_entry.command.startswith("shout "):
                shout_message = command_entry.command[len("shout ") :]
                other_agents_in_room = Agent.objects.exclude(
                    id=command_entry.agent.id
                ).filter(
                    location=command_entry.agent.location,  # Filter by location
                    last_command_sent__gte=timezone.now() - timedelta(minutes=5),
                )
                for other_agent in other_agents_in_room:
                    PerceptionQueue.objects.create(
                        agent=other_agent,
                        source_agent=command_entry.agent,
                        type="none",
                        command=command_entry,  # Link to the original command
                        text=f'{command_entry.agent.name} shouted "{shout_message}"',
                    )
            logger.info(
                f"Command {command_entry.command} for agent {command_entry.agent.name} finished with status: {command_entry.status}"
            )
        except Exception as e:
            logger.error(
                f"Error processing command {command_entry.command} for agent {command_entry.agent.name}: {e}",
                exc_info=True,
            )
            command_entry.status = "failed"
            command_entry.output = f"Error: {e}"
            command_entry.save()

    def handle(self, *args, **options):
        logger.info("Starting command queue worker...")
        while True:
            try:
                pending_commands = CommandQueue.objects.filter(
                    status="pending"
                ).order_by("date")
                if pending_commands.exists():
                    command_entry = pending_commands.first()
                    self._process_single_command(command_entry)
            except Exception as e:
                logger.error(f"Error in command worker loop: {e}", exc_info=True)
            time.sleep(1)  # Poll every second
