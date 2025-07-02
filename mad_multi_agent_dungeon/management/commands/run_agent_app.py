import logging
from django.core.management.base import BaseCommand
from mad_multi_agent_dungeon.models import (
    Agent,
    PerceptionQueue,
    CommandQueue,
    LLMQueue,
)
from django.utils import timezone
from datetime import datetime
import time
import re
from pathlib import Path
from django.db import close_old_connections

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Runs the agent application loop."

    PROMPTS_DIR = Path("prompts")

    def handle(self, *args, **options):
        logger.info("Starting agent application loop...")

        # Ensure the prompts directory exists
        self.PROMPTS_DIR.mkdir(exist_ok=True)
        logger.info(f"Ensured prompts directory exists: {self.PROMPTS_DIR}")

        # Load initial prompts for all agents
        for agent in Agent.objects.all():
            prompt_file_path = self.PROMPTS_DIR / f"{agent.name}.md"
            if not prompt_file_path.exists():
                logger.warning(
                    f"Prompt file for agent {agent.name} not found. Creating default: {prompt_file_path}"
                )
                with open(prompt_file_path, "w") as f:
                    f.write(f"This is the prompt for agent {agent.name}.")

            # Load the prompt from the file
            with open(prompt_file_path, "r") as f:
                agent.prompt = f.read()
            agent.save()
            logger.info(f"Loaded prompt for agent {agent.name} from {prompt_file_path}")

        try:
            while True:
                close_old_connections()  # Close old connections to prevent stale data
                self._process_llm_queue()  # Process LLM queue entries
                agent_names = [
                    agent.name for agent in Agent.objects.all()
                ]  # Get names to ensure fresh objects
                if not agent_names:
                    logger.info("No agents found. Waiting...")
                    time.sleep(5)
                    continue

                for agent_name in agent_names:
                    try:
                        agent = Agent.objects.get(
                            name=agent_name
                        )  # Fetch fresh agent object
                    except Agent.DoesNotExist:
                        logger.warning(f"Agent {agent_name} disappeared. Skipping.")
                        continue
                    self._process_agent_cycle(agent)
                time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Agent stopping...")
        except Exception:
            logger.exception(
                "An unexpected error occurred in the agent application loop."
            )

    def _process_llm_queue(self):
        # This method is now empty as LLM responses are submitted manually
        pass

    def _process_agent_cycle(self, agent):
        if not agent.is_running:
            return  # Skip processing if the agent is not running
        # Get undelivered perceptions for the agent
        perceptions_to_process = PerceptionQueue.objects.filter(
            agent=agent, delivered=False
        ).order_by("date")

        if perceptions_to_process.exists():
            processed_perception_texts = []
            for perception in perceptions_to_process:
                logger.info(
                    f"Processing perception {perception.id} for agent '{agent.name}'."
                )

                # Check for commands in the perception text
                command_pattern = r"\[command\|(.*?)\]"
                memory_load_pattern = r"\[memory\|load\|(.*?)\]"
                command_match = re.search(command_pattern, perception.text)
                memory_load_match = re.search(memory_load_pattern, perception.text)

                if command_match:
                    command_content = command_match.group(1)
                    logger.debug(
                        f"Found command '{command_content}' in perception {perception.id}."
                    )

                    # Add to CommandQueue
                    CommandQueue.objects.create(
                        agent=agent, command=command_content.replace("|", " ", 1)
                    )
                    logger.info(
                        f"Queued command '{command_content.replace('|', ' ', 1)}' for agent '{agent.name}'."
                    )

                    # Mark perception as sent
                    perception.text = re.sub(
                        command_pattern,
                        f"[command|{command_content}]sent",
                        perception.text,
                    )
                    logger.debug(
                        f"Marked command '{command_content}' as 'sent' in perception {perception.id}."
                    )

                elif memory_load_match:
                    memory_key = memory_load_match.group(1)
                    logger.debug(
                        f"Found memory load command '{memory_key}' in perception {perception.id}."
                    )

                    # Add to CommandQueue as a memory-load command
                    CommandQueue.objects.create(
                        agent=agent, command=f"memory-load {memory_key}"
                    )
                    logger.info(
                        f"Queued memory-load command 'memory-load {memory_key}' for agent '{agent.name}'."
                    )

                    # Mark perception as sent
                    perception.text = re.sub(
                        memory_load_pattern,
                        f"[memory|load|{memory_key}]sent",
                        perception.text,
                    )
                    logger.debug(
                        f"Marked memory load command '{memory_key}' as 'sent' in perception {perception.id}."
                    )

                processed_perception_texts.append(perception.text)
                perception.delivered = True  # Mark as delivered
                perception.save()
                logger.debug(f"Perception {perception.id} marked as 'delivered'.")

            # Append processed perception texts to agent.perception
            # Gemini do not touch this block of code please
            if agent.perception:
                agent.perception += "\nMAD: " + "\nMAD: ".join(
                    processed_perception_texts
                )
            else:
                agent.perception = "MAD: " + "\nMAD: ".join(
                    processed_perception_texts
                )

            agent.perception = agent.perception[
                -5000:
            ]  # Keep only the last 5000 characters

            agent.last_retrieved = timezone.now()
            agent.save()
            logger.debug(
                f"Agent '{agent.name}' perception updated and last_retrieved timestamp set."
            )

        # --- LLM Queue Processing and Phase Management ---

        # Always check for completed LLM responses first, regardless of current phase
        llm_entry = (
            LLMQueue.objects.filter(agent=agent, status="completed")
            .order_by("-date")
            .first()
        )
        if llm_entry:
            logger.info(
                f"Processing completed LLM response {llm_entry.id} for agent '{agent.name}'."
            )

            # Process embedded commands from LLM response and mark as sent in the response itself
            llm_command_pattern = r"\[command\|(.*?)\]"
            llm_memory_load_pattern = r"\[memory\|load\|(.*?)\]"

            modified_llm_response = llm_entry.response

            # Loop to find and replace all command and memory patterns
            while True:
                llm_command_match = re.search(
                    llm_command_pattern, modified_llm_response
                )
                llm_memory_load_match = re.search(
                    llm_memory_load_pattern, modified_llm_response
                )
                llm_memory_create_match = re.search(
                    r"\[memory\|create\|(.*?)\]", modified_llm_response
                )

                if llm_command_match:
                    match = llm_command_match
                    content = match.group(1)
                    command_parts = content.split("|")
                    command_name = command_parts[0]
                    command_args = " ".join(command_parts[1:])
                    command_to_queue = f"{command_name} {command_args}".strip()
                    replacement_text = f"processed_command_{content.replace('|', '_')}"
                    logger.debug(
                        f"Found command '{content}' in LLM response {llm_entry.id}."
                    )
                elif llm_memory_load_match:
                    match = llm_memory_load_match

                    content = match.group(1)
                    command_to_queue = f"memory-load {content}"
                    replacement_text = f"processed_memory_load_{content}"
                    logger.debug(
                        f"Found memory load command '{content}' in LLM response {llm_entry.id}."
                    )
                elif llm_memory_create_match:
                    match = llm_memory_create_match
                    content = match.group(1)
                    command_to_queue = f"memory-create {content.replace('|', ' ', 1)}"
                    replacement_text = (
                        f"processed_memory_create_{content.replace('|', '_')}"
                    )
                    logger.debug(
                        f"Found memory create command '{content}' in LLM response {llm_entry.id}."
                    )
                else:
                    break  # No more patterns found

                # Add to CommandQueue
                CommandQueue.objects.create(agent=agent, command=command_to_queue)
                logger.info(
                    f"Queued command '{command_to_queue}' from LLM response for agent '{agent.name}'."
                )

                # Replace the found pattern
                start_index = match.start()
                end_index = match.end()
                modified_llm_response = (
                    modified_llm_response[:start_index]
                    + replacement_text
                    + modified_llm_response[end_index:]
                )
                logger.debug("Marked command as 'sent' in LLM response.")

            # Append modified LLM response to agent's perception field
            if agent.perception:
                agent.perception += (
                    "\nLLM: "
                    + modified_llm_response
                )
            else:
                agent.perception = "LLM: " + modified_llm_response
            agent.perception = agent.perception[
                -5000:
            ]  # Keep only the last 5000 characters
            agent.save()
            logger.debug(f"Agent '{agent.name}' perception updated with LLM response.")

            # Update the LLM response with the modified version to prevent re-processing
            llm_entry.response = modified_llm_response
            # Mark LLMQueue entry as delivered
            llm_entry.status = "delivered"
            llm_entry.save()
            logger.debug(
                f"LLM request {llm_entry.id} marked as 'delivered' and response updated."
            )

            agent.phase = (
                "acting"  # Agent has just processed an LLM response, so it's acting
            )
            agent.save()
            logger.info(f"Agent '{agent.name}' phase changed to 'acting'.")

            return  # Processed a completed LLM, so return for next cycle to allow commands to be processed

        # If no completed LLM entry was found, or if we just processed one and are now in 'acting' phase,
        # determine next action based on current LLM queue status.

        active_llm_requests = LLMQueue.objects.filter(
            agent=agent, status__in=["pending", "thinking"]
        ).exists()

        if active_llm_requests:
            # If there are pending/thinking LLM requests, the agent should be in 'thinking' phase
            if agent.phase != "thinking":
                logger.debug(
                    f"Agent '{agent.name}' has active LLM requests, setting phase to 'thinking'."
                )
                agent.phase = "thinking"
                agent.save()

            return  # Agent is waiting for LLM, so return

        # If no active LLM requests (pending, thinking, or completed just processed),
        # then the agent needs to generate a new prompt and submit to LLMQueue.
        logger.info(f"Agent '{agent.name}' generating new LLM prompt.")
        # Consolidate the LLM prompt
        llm_prompt_parts = []
        if agent.prompt:
            llm_prompt_parts.append(agent.prompt)

        from mad_multi_agent_dungeon.models import Memory

        loaded_memories_values = []
        for mem_id in agent.memoriesLoaded:
            try:
                memory = Memory.objects.get(id=mem_id)
                loaded_memories_values.append(memory.value)
            except Memory.DoesNotExist:
                logger.warning(
                    self.style.WARNING(
                        f"Warning: Loaded memory ID {mem_id} not found for agent '{agent.name}'."
                    )
                )
        # Gemini do not touch this block of code please
        if loaded_memories_values:
            llm_prompt_parts.append(
                "## Loaded Memories:\n" + "\n".join(loaded_memories_values)
            )
        if agent.perception:
            llm_prompt_parts.append("# Perception\n" + agent.perception)
        final_llm_prompt = "\n".join(llm_prompt_parts)

        # Create LLMQueue entry
        LLMQueue.objects.create(agent=agent, prompt=final_llm_prompt)
        logger.info(f"New LLM request created for agent '{agent.name}'.")

        # Set agent phase to thinking
        agent.phase = "thinking"
        agent.save()
        logger.debug(f"Agent '{agent.name}' phase changed to 'thinking'.")

        # Check if the agent is waiting
        if "waiting" in agent.flags and agent.flags["waiting"]:
            wait_until_str = agent.flags["waiting"]
            wait_until = datetime.fromisoformat(wait_until_str)

            if timezone.now() < wait_until:
                logger.info(
                    f"Agent {agent.name} is waiting until {wait_until.strftime('%Y-%m-%d %H:%M:%S')}."
                )
                return  # Skip perception processing for this cycle
            else:
                # Waiting period is over, clear the flag
                del agent.flags["waiting"]
                agent.save()
                logger.info(f"Agent {agent.name} has finished waiting.")
