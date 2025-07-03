import logging
from django.core.management.base import BaseCommand
from mad_multi_agent_dungeon.models import (
    Agent,
    PerceptionQueue,
    CommandQueue,
    LLMQueue,
    LLMAPIKey,
)
from mad_multi_agent_dungeon.llm_api import call_gemini_api

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
        pending_llm_requests = LLMQueue.objects.filter(status="pending")
        for llm_request in pending_llm_requests:
            logger.info(f"Processing pending LLM request {llm_request.id} for agent {llm_request.agent.name}")
            llm_request.status = "thinking"
            llm_request.save()

            api_key_obj = LLMAPIKey.objects.filter(is_active=True).first()
            if not api_key_obj:
                logger.error("No active LLM API key found. Marking LLM request as failed.")
                print("DEBUG: No active LLM API key found in _process_llm_queue") # Debug print
                llm_request.status = "failed"
                llm_request.response = "Error: No active API key found."
                llm_request.save()
                continue

            try:
                response_text = call_gemini_api(
                    llm_request.prompt, api_key_obj.key, api_key_obj.parameters
                )
                llm_request.response = response_text
                llm_request.status = "completed"
                api_key_obj.last_used = timezone.now()
                api_key_obj.usage_count += 1
                api_key_obj.save()
                logger.info(f"LLM request {llm_request.id} completed for agent {llm_request.agent.name}.")
            except Exception as e:
                logger.error(f"Error calling LLM API for request {llm_request.id}: {e}")
                llm_request.response = f"Error: {e}"
                llm_request.status = "failed"
            llm_request.save()

    def _process_agent_cycle(self, agent):
        agent.perception = agent.perception or "" # Ensure perception is a string
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
                f"Processing completed LLM response {llm_entry.id} for agent '{agent.name}'. (Status: {llm_entry.status})"
            )
            print(f"DEBUG: Agent {agent.name} perception BEFORE update: '{agent.perception}'") # DEBUG
            # Process embedded commands from LLM response
            original_llm_response = llm_entry.response
            llm_command_pattern = r"\[command\|(.+?)\]"
            llm_memory_load_pattern = r"\[memory\|load\|(.+?)\]"
            llm_memory_create_pattern = r"\[memory\|create\|(.+?)\]"

            # Process regular commands
            for match in re.finditer(llm_command_pattern, original_llm_response):
                command_content = match.group(1)
                command_parts = command_content.split("|")
                command_name = command_parts[0]
                command_args = " ".join(command_parts[1:])
                command_to_queue = f"{command_name} {command_args}".strip()
                CommandQueue.objects.create(agent=agent, command=command_to_queue)
                logger.info(
                    f"Queued command '{command_to_queue}' from LLM response for agent '{agent.name}'."
                )

            # Process memory-load commands
            for match in re.finditer(llm_memory_load_pattern, original_llm_response):
                memory_key = match.group(1)
                command_to_queue = f"memory-load {memory_key}"
                CommandQueue.objects.create(agent=agent, command=command_to_queue)
                logger.info(
                    f"Queued command '{command_to_queue}' from LLM response for agent '{agent.name}'."
                )

            # Process memory-create commands
            for match in re.finditer(llm_memory_create_pattern, original_llm_response):
                content = match.group(1)
                parts = content.split("|")
                if len(parts) >= 2:
                    memory_key = parts[0]
                    memory_value = "|".join(parts[1:])
                    command_to_queue = f"memory-create {memory_key} {memory_value}"
                    CommandQueue.objects.create(agent=agent, command=command_to_queue)
                    logger.info(
                        f"Queued command '{command_to_queue}' from LLM response for agent '{agent.name}'."
                    )

            # Append original LLM response to agent's perception field
            # Truncate original_llm_response to make space for "LLM: " prefix
            truncated_llm_response = original_llm_response[-4995:]
            prefixed_llm_response = "LLM: " + truncated_llm_response

            if agent.perception:
                agent.perception += "\n" + prefixed_llm_response
            else:
                agent.perception = prefixed_llm_response
            agent.perception = agent.perception[
                -5000:
            ]  # Keep only the last 5000 characters
            agent.save()
            logger.debug(f"Agent '{agent.name}' perception updated with LLM response.")
            print(f"DEBUG: Agent {agent.name} perception AFTER update: '{agent.perception}'") # DEBUG

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

        print(f"DEBUG: No completed LLM entry found for agent {agent.name} or already delivered.") # DEBUG

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
        if agent.memoriesLoaded:  # Check if memoriesLoaded is not None
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

        if not agent.is_running:
            logger.info(f"Agent '{agent.name}' is not running. Halting for inspection. Prompt that would have been sent:\n{final_llm_prompt}")
            time.sleep(5) # Sleep to prevent rapid logging
            return # Skip processing if the agent is not running

        # Create LLMQueue entry
        LLMQueue.objects.create(agent=agent, prompt=final_llm_prompt)
        logger.info(f"New LLM request created for agent '{agent.name}'.")

        # Set agent phase to thinking
        agent.phase = "thinking"
        agent.is_running = False # Pause the agent after creating an LLM request
        agent.save()
        logger.debug(f"Agent '{agent.name}' phase changed to 'thinking' and is_running set to False.")

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
