from django.core.management.base import BaseCommand
from mad_multi_agent_dungeon.models import Agent, PerceptionQueue, CommandQueue, LLMQueue
from django.utils import timezone
from datetime import datetime, timedelta
import time
import re
import os
from pathlib import Path
from django.db import connections, close_old_connections

class Command(BaseCommand):
    help = 'Runs the agent application loop.'

    PROMPTS_DIR = Path('prompts')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Agent app started. Loading all agents...'))

        # Ensure the prompts directory exists
        self.PROMPTS_DIR.mkdir(exist_ok=True)

        # Load initial prompts for all agents
        for agent in Agent.objects.all():
            prompt_file_path = self.PROMPTS_DIR / f'{agent.name}.md'
            if not prompt_file_path.exists():
                # Create the file if it doesn't exist
                with open(prompt_file_path, 'w') as f:
                    f.write(f"This is the prompt for agent {agent.name}.")
                self.stdout.write(self.style.NOTICE(f"Created prompt file for {agent.name} at {prompt_file_path}"))
            
            # Load the prompt from the file
            with open(prompt_file_path, 'r') as f:
                agent.prompt = f.read()
            agent.save()
            self.stdout.write(self.style.SUCCESS(f"Loaded prompt for {agent.name} from {prompt_file_path}"))

        while True:
            close_old_connections() # Close old connections to prevent stale data
            self._process_llm_queue() # Process LLM queue entries
            agent_names = [agent.name for agent in Agent.objects.all()] # Get names to ensure fresh objects
            if not agent_names:
                self.stdout.write(self.style.NOTICE("No agents found. Waiting for agents to be created..."))
                time.sleep(5)
                continue

            for agent_name in agent_names:
                try:
                    agent = Agent.objects.get(name=agent_name) # Fetch fresh agent object
                except Agent.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"Agent {agent_name} not found. Skipping."))
                    continue
                self._process_agent_cycle(agent)
            time.sleep(5)

    def _process_llm_queue(self):
        pending_llm_entries = LLMQueue.objects.filter(status='pending')
        for entry in pending_llm_entries:
            # Simulate LLM response
            simulated_response = f"LLM response for: {entry.prompt[:100]}..."
            entry.response = simulated_response
            entry.status = 'completed'
            entry.save()
            self.stdout.write(self.style.SUCCESS(f"Processed LLMQueue entry for {entry.agent.name}. Status: {entry.status}"))

    def _process_agent_cycle(self, agent):
        self.stdout.write(self.style.NOTICE(f"Agent {agent.name} is_running: {agent.is_running}")) # Debug print
        if not agent.is_running:
            return # Skip processing if the agent is not running
        current_perception_text = ""
        # Get undelivered perceptions for the agent
        perceptions_to_process = PerceptionQueue.objects.filter(agent=agent, delivered=False).order_by('date')
    
        if perceptions_to_process.exists():
            for perception in perceptions_to_process:
                self.stdout.write(self.style.SUCCESS(f"Perception: {perception.text}"))
                
                # Check for commands in the perception text
                command_pattern = r"^\[command\|(.*?)\]"
                memory_load_pattern = r"^\[memory\|load\|(.*?)\]"

                command_match = re.search(command_pattern, perception.text)
                memory_load_match = re.search(memory_load_pattern, perception.text)
                
                if command_match:
                    command_content = command_match.group(1)
                    self.stdout.write(self.style.SUCCESS(f"Found command: {command_content}"))
                    
                    # Add to CommandQueue
                    CommandQueue.objects.create(agent=agent, command=command_content.replace('|', ' ', 1))
                    self.stdout.write(self.style.SUCCESS(f"Command '{command_content}' added to CommandQueue."))
                    
                    # Mark perception as sent
                    perception.text = re.sub(command_pattern, f"[command|{command_content}]sent", perception.text)
                    self.stdout.write(self.style.SUCCESS(f"Perception text updated to: {perception.text}"))
                elif memory_load_match:
                    memory_key = memory_load_match.group(1)
                    self.stdout.write(self.style.SUCCESS(f"Found memory load command: {memory_key}"))

                    # Add to CommandQueue as a memory-load command
                    CommandQueue.objects.create(agent=agent, command=f"memory-load {memory_key}")
                    self.stdout.write(self.style.SUCCESS(f"Command 'memory-load {memory_key}' added to CommandQueue."))
                    self.stdout.write(self.style.NOTICE(f"DEBUG: CommandQueue entry created for memory-load {memory_key}"))

                    # Mark perception as sent
                    perception.text = re.sub(memory_load_pattern, f"[memory|load|{memory_key}]sent", perception.text)
                    self.stdout.write(self.style.SUCCESS(f"Perception text updated to: {perception.text}"))

                perception.delivered = True # Mark as delivered
                perception.save()
            
            agent.last_retrieved = timezone.now()
            agent.save()

        # Check if the agent is in the 'thinking' phase
        if agent.phase == 'thinking':
            # Look for a completed LLMQueue entry for this agent
            llm_entry = LLMQueue.objects.filter(agent=agent, status='completed').order_by('-date').first()
            if llm_entry:
                self.stdout.write(self.style.SUCCESS(f"LLM response completed for {agent.name}. Appending to perception."))
                self.stdout.write(self.style.NOTICE(f"LLM Response content (first 100 chars): {llm_entry.response[:100]}..."))
                self.stdout.write(self.style.NOTICE(f"Agent perception BEFORE update (first 100 chars): {agent.perception[:100] if agent.perception else 'EMPTY'}..."))
                # Append LLM response to agent's perception field
                if agent.perception:
                    agent.perception += "\n" + llm_entry.response
                else:
                    agent.perception = llm_entry.response
                agent.perception = agent.perception[-5000:] # Keep only the last 5000 characters
                agent.save()
                self.stdout.write(self.style.NOTICE(f"Agent perception AFTER update (first 100 chars): {agent.perception[:100]}..."))

                # Process embedded commands from LLM response
                # Use a non-greedy match for the command content
                llm_command_pattern = r"\\[command\\|(.*?)\\]"
                llm_memory_load_pattern = r"\\[memory\\|load\\|(.*?)\\]"

                # Find all command matches
                for match in re.finditer(llm_command_pattern, llm_entry.response):
                    command_content = match.group(1)
                    CommandQueue.objects.create(agent=agent, command=command_content.replace('|', ' ', 1))
                    self.stdout.write(self.style.SUCCESS(f"LLM embedded command '{command_content}' added to CommandQueue."))

                # Find all memory load matches
                for match in re.finditer(llm_memory_load_pattern, llm_entry.response):
                    memory_key = match.group(1)
                    CommandQueue.objects.create(agent=agent, command=f"memory-load {memory_key}")
                    self.stdout.write(self.style.SUCCESS(f"LLM embedded memory-load '{memory_key}' added to CommandQueue."))

                # Mark LLMQueue entry as delivered
                llm_entry.status = 'delivered'
                llm_entry.save()

                agent.phase = 'acting'
                agent.save()
                self.stdout.write(self.style.SUCCESS(f"Agent {agent.name} phase changed to 'acting'."))
            else:
                # If still thinking and no completed entry, just wait.
                self.stdout.write(self.style.NOTICE(f"Agent {agent.name} is thinking... Waiting for LLM response."))
            return # Return to wait for the next cycle, preventing new LLMQueue entries

        # Check if the agent is waiting
        if 'waiting' in agent.flags and agent.flags['waiting']:
            wait_until_str = agent.flags['waiting']
            wait_until = datetime.fromisoformat(wait_until_str)
            
            if timezone.now() < wait_until:
                self.stdout.write(self.style.NOTICE(f"Agent {agent.name} is waiting until {wait_until.strftime('%Y-%m-%d %H:%M:%S')}."))
                return # Skip perception processing for this cycle
            else:
                # Waiting period is over, clear the flag
                del agent.flags['waiting']
                agent.save()
                self.stdout.write(self.style.SUCCESS(f"Agent {agent.name} has finished waiting."))

        # Construct the LLM prompt
        llm_prompt_parts = []
        if agent.prompt:
            llm_prompt_parts.append(agent.prompt)
        
        # Add loaded memories
        from mad_multi_agent_dungeon.models import Memory # Import Memory model here to avoid circular imports
        loaded_memories_values = []
        for mem_id in agent.memoriesLoaded:
            try:
                memory = Memory.objects.get(id=mem_id)
                loaded_memories_values.append(memory.value)
            except Memory.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Warning: Loaded memory ID {mem_id} not found."))
        if loaded_memories_values:
            llm_prompt_parts.append("\n---\nLoaded Memories:\n" + "\n".join(loaded_memories_values))

        # Add agent's accumulated perception
        if agent.perception:
            llm_prompt_parts.append("\n---\nAgent Perception History:\n" + agent.perception)

        final_llm_prompt = "\n".join(llm_prompt_parts)

        # Create LLMQueue entry
        LLMQueue.objects.create(agent=agent, prompt=final_llm_prompt)
        self.stdout.write(self.style.SUCCESS(f"LLMQueue entry created for {agent.name}. Prompt length: {len(final_llm_prompt)} "))

        # Set agent phase to thinking
        agent.phase = 'thinking'
        agent.save()