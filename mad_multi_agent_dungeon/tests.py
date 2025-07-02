import json
from pathlib import Path
from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from mad_multi_agent_dungeon.models import Agent, CommandQueue, ObjectInstance, PerceptionQueue, LLMQueue, Memory
from mad_multi_agent_dungeon.commands import handle_command, MAP_DATA, OBJECT_DATA
from mad_multi_agent_dungeon.management.commands.run_command_worker import Command as CommandWorker

class IndexViewTest(TestCase):
    def test_index_view(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Agents")

class AgentModelTest(TestCase):
    def test_create_agent(self):
        agent = Agent.objects.create(
            name="TestAgent",
            look="A test agent.",
            description="This is a test agent for the Multi Agent Dungeon.",
            flags={"meditating": "2025-06-30"},
            inventory=["item1", "item2"],
            tokens=100,
            level=1,
            location="start_room"
        )
        self.assertEqual(agent.name, "TestAgent")
        self.assertEqual(agent.look, "A test agent.")
        self.assertEqual(agent.description, "This is a test agent for the Multi Agent Dungeon.")
        self.assertEqual(agent.flags, {"meditating": "2025-06-30"})
        self.assertEqual(agent.inventory, ["item1", "item2"])
        self.assertEqual(agent.tokens, 100)
        self.assertEqual(agent.level, 1)
        self.assertEqual(agent.location, "start_room")
        self.assertIsNotNone(agent.pk)

    def test_unique_name(self):
        Agent.objects.create(name="UniqueAgent", look="a", description="b", tokens=0, level=0, location="room_a")
        with self.assertRaises(Exception): # IntegrityError or similar
            Agent.objects.create(name="UniqueAgent", look="c", description="d", tokens=0, level=0, location="room_b")

    def test_is_active_function(self):
        # Agent is active if last_command_sent is within the last 5 minutes
        active_agent = Agent.objects.create(
            name="ActiveAgent",
            look="An active agent.",
            description="",
            tokens=0,
            level=0,
            location="start_room",
            last_command_sent=timezone.now() - timedelta(minutes=2)
        )
        self.assertTrue(active_agent.is_active())

        # Agent is not active if last_command_sent is older than 5 minutes
        inactive_agent = Agent.objects.create(
            name="InactiveAgent",
            look="An inactive agent.",
            description="",
            tokens=0,
            level=0,
            location="start_room",
            last_command_sent=timezone.now() - timedelta(minutes=6)
        )
        self.assertFalse(inactive_agent.is_active())

        # Agent is not active if last_command_sent is None
        never_commanded_agent = Agent.objects.create(
            name="NeverCommandedAgent",
            look="A new agent.",
            description="",
            tokens=0,
            level=0,
            location="start_room",
            last_command_sent=None
        )
        self.assertFalse(never_commanded_agent.is_active())

class CommandQueueModelTest(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(
            name="TestAgentForCommand",
            look="A test agent for commands.",
            description="This agent is for testing commands.",
            tokens=0,
            level=0,
            location="test_room"
        )

    def test_create_command(self):
        command_entry = CommandQueue.objects.create(
            command="ping",
            agent=self.agent,
            status="pending",
            output=""
        )
        self.assertEqual(command_entry.command, "ping")
        self.assertEqual(command_entry.agent, self.agent)
        self.assertEqual(command_entry.status, "pending")
        self.assertEqual(command_entry.output, "")
        self.assertIsNotNone(command_entry.date)
        self.assertIsNotNone(command_entry.id)

    def test_command_status_choices(self):
        command_entry = CommandQueue.objects.create(
            command="test",
            agent=self.agent,
            status="processing",
            output=""
        )
        self.assertEqual(command_entry.status, "processing")

        command_entry.status = "completed"
        command_entry.save()
        self.assertEqual(command_entry.status, "completed")

        command_entry.status = "delivered"
        command_entry.save()
        self.assertEqual(command_entry.status, "delivered")

        command_entry.status = "failed"
        command_entry.save()
        self.assertEqual(command_entry.status, "failed")

        with self.assertRaises(Exception): # ValidationError
            command_entry.status = "invalid_status"
            command_entry.full_clean()



class AgentAppIntegrationTest(TestCase):
    def setUp(self):
        self.agent_name = "TestAgent"
        self.prompt_dir = Path('/home/edward/Desktop/mad-django/prompts')
        self.prompt_file = self.prompt_dir / f'{self.agent_name}.md'

        # Ensure a clean state for the agent and prompt file
        Agent.objects.filter(name=self.agent_name).delete()
        if self.prompt_file.exists():
            self.prompt_file.unlink()

        self.agent = Agent.objects.create(
            name=self.agent_name,
            look="A test agent for app integration.",
            description="",
            tokens=0,
            level=0,
            location="start_room",
            phase='idle'
        )
        # Create a dummy prompt file
        with open(self.prompt_file, 'w') as f:
            f.write("Base prompt content.")

        # Create a test memory
        self.test_memory = Memory.objects.create(
            agent=self.agent,
            key="test_key",
            value="Test memory value."
        )

        # Clear queues before each test
        LLMQueue.objects.all().delete()
        CommandQueue.objects.all().delete()
        PerceptionQueue.objects.all().delete()

    def tearDown(self):
        # Clean up the created prompt file
        if self.prompt_file.exists():
            self.prompt_file.unlink()

    def test_agent_prompt_generation_and_llm_queue_submission(self):
        # Simulate the agent app running for one cycle
        # We need to call the handle method of the Command class directly
        # as running it via manage.py would start an infinite loop.
        from mad_multi_agent_dungeon.management.commands.run_agent_app import Command as AgentAppCommand
        agent_app_command = AgentAppCommand()
        
        # Manually call handle, but we need to mock the infinite loop behavior
        # For this test, we only care about the first iteration
        # The agent app loads prompts and creates the first LLMQueue entry
        # Ensure the agent's prompt is loaded from the file
        with open(self.prompt_file, 'r') as f:
            self.agent.prompt = f.read()
        self.agent.save()

        # Ensure memories are loaded for the prompt generation
        self.agent.memoriesLoaded = [self.test_memory.id]
        self.agent.save()

        agent_app_command._process_agent_cycle(self.agent)

        # Refresh agent to get updated state
        self.agent.refresh_from_db()

        # Assert agent phase is thinking
        self.assertEqual(self.agent.phase, 'thinking')

        # Assert LLMQueue entry was created
        llm_entry = LLMQueue.objects.filter(agent=self.agent).order_by('-date').first()
        self.assertIsNotNone(llm_entry)
        self.assertEqual(llm_entry.status, 'pending') # Agent phase is thinking, so LLMQueue status should be thinking

        expected_prompt = "Base prompt content.\n## Loaded Memories:\nTest memory value."
        print(f"Actual LLM Prompt: {llm_entry.prompt}")
        self.assertEqual(llm_entry.prompt.strip(), expected_prompt.strip())

    def test_llm_response_processing_and_perception_update(self):
        from mad_multi_agent_dungeon.management.commands.run_agent_app import Command as AgentAppCommand
        agent_app_command = AgentAppCommand()

        # First, simulate the initial prompt generation and LLMQueue submission
        agent_app_command._process_agent_cycle(self.agent)
        self.agent.refresh_from_db()
        llm_entry = LLMQueue.objects.filter(agent=self.agent).order_by('-date').first()

        # Simulate LLM response
        llm_entry.status = 'completed'
        llm_entry.response = "LLM says: Hello! [command|say|Hello from LLM!] [memory|create|llm_key|llm_value]"
        llm_entry.save()

        # Run agent app again to process the completed LLM response
        # Run agent app again to process the completed LLM response
        agent_app_command._process_agent_cycle(self.agent) # This processes the LLM response and changes phase to 'acting'
        self.agent.refresh_from_db()
        llm_entry.refresh_from_db()

        # Assert agent's perception is updated
        self.assertIn("LLM says: Hello!", self.agent.perception)
        # Check that the command was processed and marked as such in the perception
        self.agent.refresh_from_db()
        self.assertIn("processed_command_say_Hello from LLM!", self.agent.perception)
        self.assertIn("processed_memory_create_llm_key_llm_value", self.agent.perception)

        # Assert agent phase is 'acting'
        self.assertEqual(self.agent.phase, 'acting')

        # Run agent app a third time to process the newly added perception with embedded commands
        agent_app_command._process_agent_cycle(self.agent)
        self.agent.refresh_from_db()

        # Assert LLMQueue entry is marked as 'delivered'
        self.assertEqual(llm_entry.status, 'delivered')

        # Assert CommandQueue entries were created for both commands
        say_command_entry = CommandQueue.objects.filter(agent=self.agent, command='say Hello from LLM!').first()
        self.assertIsNotNone(say_command_entry)
        self.assertEqual(say_command_entry.status, 'pending')

        memory_create_command_entry = CommandQueue.objects.filter(agent=self.agent, command='memory-create llm_key llm_value').first()
        self.assertIsNotNone(memory_create_command_entry)
        self.assertEqual(memory_create_command_entry.status, 'pending')

    def test_perception_queue_processing_and_command_creation(self):
        from mad_multi_agent_dungeon.management.commands.run_agent_app import Command as AgentAppCommand
        agent_app_command = AgentAppCommand()

        # Create a perception with an embedded command
        PerceptionQueue.objects.create(
            agent=self.agent,
            text="[command|look]"
        )
        # Create a perception with an embedded memory load command
        PerceptionQueue.objects.create(
            agent=self.agent,
            text=f"[memory|load|{self.test_memory.key}]"
        )

        # Run agent app to process perceptions
        agent_app_command._process_agent_cycle(self.agent)
        self.agent.refresh_from_db()

        # Assert CommandQueue entry was created for 'look'
        look_command = CommandQueue.objects.filter(agent=self.agent, command='look').first()
        self.assertIsNotNone(look_command)
        self.assertEqual(look_command.status, 'pending')

        # Assert CommandQueue entry was created for 'memory-load'
        memory_load_command = CommandQueue.objects.filter(agent=self.agent, command=f'memory-load {self.test_memory.key}').first()
        print(f"DEBUG: memory_load_command: {memory_load_command}")
        print(f"DEBUG: Commands in queue for agent: {list(CommandQueue.objects.filter(agent=self.agent).values_list('command', flat=True))}")
        self.assertIsNotNone(memory_load_command)
        self.assertEqual(memory_load_command.status, 'pending')

        # Assert perceptions are marked as delivered
        for perception in PerceptionQueue.objects.filter(agent=self.agent):
            self.assertTrue(perception.delivered)

        # Assert that the 'memory-load' command is in the queue, but the memory is not yet loaded
        self.assertTrue(CommandQueue.objects.filter(agent=self.agent, command=f'memory-load {self.test_memory.key}').exists())
        self.agent.refresh_from_db()
        self.assertNotIn(self.test_memory.id, self.agent.memoriesLoaded)

    def test_perception_truncation(self):
        from mad_multi_agent_dungeon.management.commands.run_agent_app import Command as AgentAppCommand
        agent_app_command = AgentAppCommand()

        # Simulate a long LLM response
        long_response = "a" * 6000  # Longer than 5000

        # Simulate the initial prompt generation and LLMQueue submission
        agent_app_command._process_agent_cycle(self.agent)
        self.agent.refresh_from_db()
        llm_entry = LLMQueue.objects.filter(agent=self.agent).order_by('-date').first()

        # Simulate LLM response
        llm_entry.status = 'completed'
        llm_entry.response = long_response
        llm_entry.save()

        # Run agent app again to process the completed LLM response
        agent_app_command._process_agent_cycle(self.agent)
        self.agent.refresh_from_db()

        # Assert agent's perception is truncated to 5000 characters
        self.assertEqual(len(self.agent.perception), 5000)
        self.assertEqual(self.agent.perception, long_response[-5000:])




    

class CommandHandlerTest(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(
            name="TestAgentForHandler",
            look="A test agent for handlers.",
            description="This agent is for testing command handlers.",
            tokens=0,
            level=0,
            location="handler_room"
        )
        self._setup_map_data()

    def _setup_map_data(self):
        # Clear and reload MAP_DATA and OBJECT_DATA for each test
        MAP_DATA['rooms'].clear()
        OBJECT_DATA.clear()

        # Load original data from files
        MAP_DATA.update(json.loads(Path('/home/edward/Desktop/mad-django/mad_multi_agent_dungeon/data/map.json').read_text()))
        OBJECT_DATA.update(json.loads(Path('/home/edward/Desktop/mad-django/mad_multi_agent_dungeon/data/objects.json').read_text()))

        # Add dummy room for testing purposes
        dummy_room_id = "dummy_room_001"
        dummy_room_title = "A Test Room"
        dummy_room_description = "This is a room for testing the look command."
        MAP_DATA['rooms'][dummy_room_id] = {
            "title": dummy_room_title,
            "description": dummy_room_description,
            "exits": {}
        }

        # Add dummy rooms for movement tests
        room_a_id = "room_A"
        room_a_title = "Room A"
        room_a_description = "This is room A."
        room_a_exits = {"north": "room_B", "south": "room_C", "west": "room_E", "up": "room_F", "down": "room_A"}

        room_b_id = "room_B"
        room_b_title = "Room B"
        room_b_description = "This is room B."
        room_b_exits = {"south": "room_A"}

        room_c_id = "room_C"
        room_c_title = "Room C"
        room_c_description = "This is room C."
        room_c_exits = {"north": "room_A"}

        room_d_id = "room_D"
        room_d_title = "Room D"
        room_d_description = "This is room D."
        room_d_exits = {"west": "room_A"}

        room_e_id = "room_E"
        room_e_title = "Room E"
        room_e_description = "This is room E."
        room_e_exits = {"east": "room_A"}

        room_f_id = "room_F"
        room_f_title = "Room F"
        room_f_description = "This is room F."
        room_f_exits = {"down": "room_A"}

        MAP_DATA['rooms'][room_a_id] = {"title": room_a_title, "description": room_a_description, "exits": room_a_exits}
        MAP_DATA['rooms'][room_b_id] = {"title": room_b_title, "description": room_b_description, "exits": room_b_exits}
        MAP_DATA['rooms'][room_c_id] = {"title": room_c_title, "description": room_c_description, "exits": room_c_exits}
        MAP_DATA['rooms'][room_d_id] = {"title": room_d_title, "description": room_d_description, "exits": room_d_exits}
        MAP_DATA['rooms'][room_e_id] = {"title": room_e_title, "description": room_e_description, "exits": room_e_exits}
        MAP_DATA['rooms'][room_f_id] = {"title": room_f_title, "description": room_f_description, "exits": room_f_exits}

        # Add room with item for examine test
        room_with_item_id = "room_with_item"
        MAP_DATA['rooms'][room_with_item_id] = {
            "title": "Room with Item",
            "description": "A room containing a sword.",
            "exits": {},
            "items": {
                "dummy_sword": {
                    "name": "dummy_sword",
                    "description": "A sharp, well-balanced sword."
                }
            }
        }
        # Ensure dummy_sword is in OBJECT_DATA for examine test
        OBJECT_DATA["dummy_sword"] = {
            "name": "dummy_sword",
            "description": "A sharp, well-balanced sword."
        }

        # Add room with mirror for use test
        room_with_mirror_id = "room_with_mirror"
        MAP_DATA['rooms'][room_with_mirror_id] = {
            "title": "Room with Mirror",
            "description": "A room with a magical mirror.",
            "exits": {},
            "items": {
                "mirror_001": {
                    "name": "mirror",
                    "description": "A shimmering mirror.",
                    "triggers": {
                        "use": {
                            "type": "response",
                            "value": "You gaze into the mirror and see your reflection."
                        }
                    }
                }
            }
        }
        # Ensure mirror_001 is in OBJECT_DATA for use test
        OBJECT_DATA["mirror_001"] = {
            "name": "mirror",
            "description": "A shimmering mirror.",
            "triggers": {
                "use": {
                    "type": "response",
                    "value": "You gaze into the mirror and see your reflection."
                }
            }
        }

    def test_ping_command_handler(self):
        command_entry = CommandQueue.objects.create(
            command="ping",
            agent=self.agent,
            status="pending",
            output=""
        )
        handle_command(command_entry)
        command_entry.refresh_from_db() # Refresh to get updated status and output
        self.assertEqual(command_entry.status, "completed")
        self.assertEqual(command_entry.output, "pong")

    def test_look_command_handler(self):
        dummy_room_id = "dummy_room_001"
        dummy_room_title = "A Test Room"
        dummy_room_description = "This is a room for testing the look command."

        self.agent.location = dummy_room_id
        self.agent.save()

        command_entry = CommandQueue.objects.create(
            command="look",
            agent=self.agent,
            status="pending",
            output=""
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()

        self.assertEqual(command_entry.status, "completed")
        self.assertIn(dummy_room_title, command_entry.output)
        self.assertIn(dummy_room_description, command_entry.output)

    def test_look_command_shows_other_agents_in_room(self):
        # Create another active agent in the same room
        other_agent = Agent.objects.create(
            name="OtherAgent",
            look="Another agent.",
            description="",
            tokens=0,
            level=0,
            location=self.agent.location, # Same room as self.agent
            last_command_sent=timezone.now() # Make the agent active
        )

        command_entry = CommandQueue.objects.create(
            command="look",
            agent=self.agent,
            status="pending",
            output=""
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()

        self.assertEqual(command_entry.status, "completed")
        self.assertIn(f"Other agents here: {other_agent.name}", command_entry.output)

    def test_look_command_shows_no_other_agents_if_none_present(self):
        # Ensure no other agents are in the room
        Agent.objects.filter(location=self.agent.location).exclude(pk=self.agent.pk).delete()

        command_entry = CommandQueue.objects.create(
            command="look",
            agent=self.agent,
            status="pending",
            output=""
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()

        self.assertEqual(command_entry.status, "completed")
        self.assertNotIn("Other agents here:", command_entry.output)
        self.assertNotIn("No other agents here.", command_entry.output) # Ensure no specific 'no agents' message unless desired

    def test_look_command_shows_objects_in_room(self):
        # Create an object instance in the same room
        ObjectInstance.objects.create(
            object_id="test_object_001",
            room_id=self.agent.location,
            data={
                "name": "Test Object",
                "description": "A test object for the room."
            }
        )

        command_entry = CommandQueue.objects.create(
            command="look",
            agent=self.agent,
            status="pending",
            output=""
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()

        self.assertEqual(command_entry.status, "completed")
        self.assertIn("Objects here: Test Object", command_entry.output)

    def test_look_command_shows_no_objects_if_none_present(self):
        # Ensure no objects are in the room
        ObjectInstance.objects.filter(room_id=self.agent.location).delete()

        command_entry = CommandQueue.objects.create(
            command="look",
            agent=self.agent,
            status="pending",
            output=""
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()

        self.assertEqual(command_entry.status, "completed")
        self.assertNotIn("Objects here:", command_entry.output)
        self.assertNotIn("No objects here.", command_entry.output) # Ensure no specific 'no objects' message unless desired

    def test_go_command_handler_invalid_move(self):
        room_a_id = "room_A"
        room_b_id = "room_B" # Agent will be in room_B after a valid move in another test

        self.agent.location = room_a_id
        self.agent.save()

        command_entry_invalid = CommandQueue.objects.create(
            command="go east",
            agent=self.agent,
            status="pending",
            output=""
        )
        handle_command(command_entry_invalid)
        command_entry_invalid.refresh_from_db()
        self.agent.refresh_from_db()

        self.assertEqual(command_entry_invalid.status, "completed")
        self.assertEqual(self.agent.location, room_a_id) # Agent should not move
        self.assertIn("You can't go east from here.", command_entry_invalid.output)

    def test_inventory_command_handler(self):
        self.agent.inventory = ["sword", "shield"]
        self.agent.save()

        command_entry_with_items = CommandQueue.objects.create(
            command="inventory",
            agent=self.agent,
            status="pending",
            output=""
        )
        handle_command(command_entry_with_items)
        command_entry_with_items.refresh_from_db()

        self.assertEqual(command_entry_with_items.status, "completed")
        self.assertIn("Your inventory:", command_entry_with_items.output)
        self.assertIn("- sword", command_entry_with_items.output)
        self.assertIn("- shield", command_entry_with_items.output)

        self.agent.inventory = []
        self.agent.save()

        command_entry_empty = CommandQueue.objects.create(
            command="inventory",
            agent=self.agent,
            status="pending",
            output=""
        )
        handle_command(command_entry_empty)
        command_entry_empty.refresh_from_db()

        self.assertEqual(command_entry_empty.status, "completed")
        self.assertEqual(command_entry_empty.output, "Your inventory is empty.")

    def test_examine_command_handler(self):
        self.agent.location = "room_with_item"
        self.agent.save()
        dummy_item_data = OBJECT_DATA["dummy_sword"]

        command_entry_examine_item = CommandQueue.objects.create(
            command="examine dummy_sword",
            agent=self.agent,
            status="pending",
            output=""
        )
        handle_command(command_entry_examine_item)
        command_entry_examine_item.refresh_from_db()

        self.assertEqual(command_entry_examine_item.status, "completed")
        self.assertEqual(command_entry_examine_item.output, dummy_item_data["description"])

        command_entry_examine_nonexistent = CommandQueue.objects.create(
            command="examine non_existent_item",
            agent=self.agent,
            status="pending",
            output=""
        )
        handle_command(command_entry_examine_nonexistent)
        command_entry_examine_nonexistent.refresh_from_db()

        self.assertEqual(command_entry_examine_nonexistent.status, "completed")
        self.assertEqual(command_entry_examine_nonexistent.output, "You don't see any 'non_existent_item' here.")

        command_entry_examine_no_item = CommandQueue.objects.create(
            command="examine",
            agent=self.agent,
            status="pending",
            output=""
        )
        handle_command(command_entry_examine_no_item)
        command_entry_examine_no_item.refresh_from_db()

        self.assertEqual(command_entry_examine_no_item.status, "failed")
        self.assertEqual(command_entry_examine_no_item.output, "Examine what?")

    def test_where_command_handler(self):
        dummy_room_id = "dummy_room_001"
        dummy_room_title = "A Test Room"
        self.agent.location = dummy_room_id
        self.agent.save()

        command_entry = CommandQueue.objects.create(
            command="where",
            agent=self.agent,
            status="pending",
            output=""
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()

        self.assertEqual(command_entry.status, "completed")
        self.assertIn(dummy_room_id, command_entry.output)
        self.assertIn(dummy_room_title, command_entry.output)

    def test_where_command_shows_other_active_agents_with_location(self):
        from datetime import timedelta
        from django.utils import timezone

        # Create active agents in different locations
        active_agent_same_room = Agent.objects.create(
            name="ActiveAgentSameRoom",
            look="", description="", tokens=0, level=0,
            location=self.agent.location,
            last_command_sent=timezone.now() - timedelta(minutes=1)
        )
        active_agent_other_room = Agent.objects.create(
            name="ActiveAgentOtherRoom",
            look="", description="", tokens=0, level=0,
            location="another_room_for_where",
            last_command_sent=timezone.now() - timedelta(minutes=1)
        )
        inactive_agent_same_room = Agent.objects.create(
            name="InactiveAgentSameRoom",
            look="", description="", tokens=0, level=0,
            location=self.agent.location,
            last_command_sent=timezone.now() - timedelta(minutes=6)
        )

        command_entry = CommandQueue.objects.create(
            command="where",
            agent=self.agent,
            status="pending",
            output=""
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()

        self.assertEqual(command_entry.status, "completed")
        self.assertIn(f"Active agents in the world:", command_entry.output)
        self.assertIn(f"- {active_agent_same_room.name} ({active_agent_same_room.location})", command_entry.output)
        self.assertIn(f"- {active_agent_other_room.name} ({active_agent_other_room.location})", command_entry.output)
        self.assertNotIn(f"- {inactive_agent_same_room.name}", command_entry.output)

    def test_where_command_shows_no_active_agents_if_none_present(self):
        # Ensure no other active agents exist
        Agent.objects.all().exclude(pk=self.agent.pk).delete()

        command_entry = CommandQueue.objects.create(
            command="where",
            agent=self.agent,
            status="pending",
            output=""
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()

        self.assertEqual(command_entry.status, "completed")
        self.assertNotIn("Active agents in the world:", command_entry.output)
        self.assertNotIn("No other active agents found.", command_entry.output) # Ensure no specific 'no agents' message unless desired

    def test_shout_command_handler_placeholder(self):
        command_entry = CommandQueue.objects.create(
            command="shout Hello",
            agent=self.agent,
            status="pending"
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()
        self.assertEqual(command_entry.status, "completed")
        self.assertEqual(command_entry.output, 'You shout: "Hello"')

    def test_use_command_handler(self):
        from .models import ObjectInstance
        import json
        from pathlib import Path
        object_data = json.loads(Path('/home/edward/Desktop/mad-django/mad_multi_agent_dungeon/data/objects.json').read_text())

        self.agent.location = "room_with_mirror"
        self.agent.save()

        ObjectInstance.objects.create(
            object_id="mirror_001",
            room_id="room_with_mirror",
            data=object_data["mirror_001"]
        )

        command_entry = CommandQueue.objects.create(
            command="use Mirror",
            agent=self.agent,
            status="pending"
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()
        self.assertEqual(command_entry.status, "completed")
        self.assertEqual(command_entry.output, object_data["mirror_001"]["triggers"]["use"]["value"])

    def test_help_command_handler(self):
        command_entry = CommandQueue.objects.create(
            command="help",
            agent=self.agent,
            status="pending"
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()
        self.assertEqual(command_entry.status, "completed")
        self.assertIn("Available commands:", command_entry.output)
        self.assertIn("ping", command_entry.output)
        self.assertIn("look", command_entry.output)
        self.assertIn("go", command_entry.output)
        self.assertIn("inventory", command_entry.output)
        self.assertIn("examine", command_entry.output)
        self.assertIn("where", command_entry.output)
        self.assertIn("shout", command_entry.output)
        self.assertIn("use", command_entry.output)
        self.assertIn("help", command_entry.output)

    

    def test_meditate_command_handler(self):
        from datetime import datetime, timedelta, timezone

        command_entry_success = CommandQueue.objects.create(
            command="meditate 5m",
            agent=self.agent,
            status="pending"
        )
        handle_command(command_entry_success)
        command_entry_success.refresh_from_db()
        self.agent.refresh_from_db()

        self.assertEqual(command_entry_success.status, "completed")
        self.assertEqual(command_entry_success.output, "You begin to meditate for 5 minutes.")
        self.assertIn("meditating", self.agent.flags)
        
        meditation_end = datetime.fromisoformat(self.agent.flags["meditating"])
        self.assertAlmostEqual(meditation_end, datetime.now(timezone.utc) + timedelta(minutes=5), delta=timedelta(seconds=5))

        command_entry_invalid = CommandQueue.objects.create(
            command="meditate 5x",
            agent=self.agent,
            status="pending"
        )
        handle_command(command_entry_invalid)
        command_entry_invalid.refresh_from_db()
        self.assertEqual(command_entry_invalid.status, "completed")
        self.assertEqual(command_entry_invalid.output, "Invalid duration format. Use 'm' for minutes or 'h' for hours.")

        command_entry_missing = CommandQueue.objects.create(
            command="meditate",
            agent=self.agent,
            status="pending"
        )
        handle_command(command_entry_missing)
        command_entry_missing.refresh_from_db()
        self.assertEqual(command_entry_missing.status, "failed")
        self.assertEqual(command_entry_missing.output, "Meditate for how long? (e.g., meditate 10m)")

    def test_directional_movement_aliases(self):
        room_a_id = "room_A"
        room_b_id = "room_B"
        room_c_id = "room_C"
        room_e_id = "room_E"
        room_f_id = "room_F"

        self.agent.location = room_a_id
        self.agent.save()

        test_cases = [
            ("north", room_b_id),
            ("n", room_b_id),
            ("south", room_c_id),
            ("s", room_c_id),
            ("east", room_a_id), # Assuming no exit to east from room_A, so agent stays
            ("e", room_a_id), # Assuming no exit to east from room_A, so agent stays
            ("west", room_e_id),
            ("w", room_e_id),
            ("up", room_f_id),
            ("u", room_f_id),
            ("down", room_a_id),
            ("d", room_a_id),
        ]

        for command_text, expected_location in test_cases:
            self.agent.location = room_a_id  # Reset agent location for each test case
            self.agent.save()
            command_entry = CommandQueue.objects.create(
                command=command_text,
                agent=self.agent,
                status="pending"
            )
            handle_command(command_entry)
            self.agent.refresh_from_db()
            self.assertEqual(self.agent.location, expected_location, f"Failed for command: {command_text}")
            command_entry.refresh_from_db()
            self.assertEqual(command_entry.status, "completed", f"Command status not completed for {command_text}")

        # Test an invalid direction
        self.agent.location = room_a_id
        self.agent.save()
        command_entry_invalid = CommandQueue.objects.create(
            command="go invalid_direction",
            agent=self.agent,
            status="pending"
        )
        handle_command(command_entry_invalid)
        command_entry_invalid.refresh_from_db()
        self.agent.refresh_from_db()
        self.assertEqual(command_entry_invalid.status, "completed")
        self.assertEqual(self.agent.location, room_a_id) # Agent should not move
        self.assertIn("You can't go invalid_direction from here.", command_entry_invalid.output)

    def test_score_command_handler(self):
        self.agent.level = 5
        self.agent.tokens = 100
        self.agent.location = "test_room"
        self.agent.save()

        command_entry = CommandQueue.objects.create(
            command="score",
            agent=self.agent,
            status="pending"
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()
        self.assertEqual(command_entry.status, "completed")
        self.assertIn(f"Name: {self.agent.name}", command_entry.output)
        self.assertIn(f"Level: {self.agent.level}", command_entry.output)
        self.assertIn(f"Tokens: {self.agent.tokens}", command_entry.output)
        self.assertIn(f"Location: {self.agent.location}", command_entry.output)

    def test_edit_profile_command_look(self):
        new_look = "a very shiny knight"
        command_entry = CommandQueue.objects.create(
            command=f"edit profile look {new_look}",
            agent=self.agent,
            status="pending"
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()
        self.agent.refresh_from_db()

        self.assertEqual(command_entry.status, "completed")
        self.assertEqual(command_entry.output, f"Your look has been updated to: {new_look}")
        self.assertEqual(self.agent.look, new_look)

    def test_edit_profile_command_description(self):
        new_description = "A brave adventurer seeking glory."
        command_entry = CommandQueue.objects.create(
            command=f"edit profile description {new_description}",
            agent=self.agent,
            status="pending"
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()
        self.agent.refresh_from_db()

        self.assertEqual(command_entry.status, "completed")
        self.assertEqual(command_entry.output, f"Your description has been updated to: {new_description}")
        self.assertEqual(self.agent.description, new_description)

    def test_edit_profile_command_invalid_field(self):
        command_entry = CommandQueue.objects.create(
            command="edit profile name NewName",
            agent=self.agent,
            status="pending"
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()

        self.assertEqual(command_entry.status, "completed")
        self.assertEqual(command_entry.output, "Invalid field. You can only edit 'look' or 'description'.")

    def test_edit_profile_command_missing_args(self):
        command_entry = CommandQueue.objects.create(
            command="edit profile look",
            agent=self.agent,
            status="pending"
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()

        self.assertEqual(command_entry.status, "failed")
        self.assertEqual(command_entry.output, "Usage: edit profile <field> <new_value> (e.g., edit profile look a tall, dark figure)")

    def test_go_command_generates_movement_perceptions(self):
        from datetime import timedelta
        from django.utils import timezone

        # Setup: Create rooms and agents
        room_a_id = "room_A"
        room_b_id = "room_B"
        room_c_id = "room_C" # A third room to ensure agents outside the immediate move are not affected

        # Agent that will move
        moving_agent = self.agent
        moving_agent.name = "MovingAgent"
        moving_agent.location = room_a_id
        moving_agent.save()

        # Active agent in the departure room (room_A)
        active_agent_in_room_a = Agent.objects.create(
            name="ActiveAgentA",
            look="", description="", tokens=0, level=0,
            location=room_a_id,
            last_command_sent=timezone.now() - timedelta(minutes=1)
        )

        # Inactive agent in the departure room (room_A)
        inactive_agent_in_room_a = Agent.objects.create(
            name="InactiveAgentA",
            look="", description="", tokens=0, level=0,
            location=room_a_id,
            last_command_sent=timezone.now() - timedelta(minutes=6)
        )

        # Active agent in the arrival room (room_B)
        active_agent_in_room_b = Agent.objects.create(
            name="ActiveAgentB",
            look="", description="", tokens=0, level=0,
            location=room_b_id,
            last_command_sent=timezone.now() - timedelta(minutes=1)
        )

        # Inactive agent in the arrival room (room_B)
        inactive_agent_in_room_b = Agent.objects.create(
            name="InactiveAgentB",
            look="", description="", tokens=0, level=0,
            location=room_b_id,
            last_command_sent=timezone.now() - timedelta(minutes=6)
        )

        # Active agent in a third room (room_C) - should not receive perceptions
        active_agent_in_room_c = Agent.objects.create(
            name="ActiveAgentC",
            look="", description="", tokens=0, level=0,
            location=room_c_id,
            last_command_sent=timezone.now() - timedelta(minutes=1)
        )

        # Clear any existing perceptions to ensure a clean test environment
        PerceptionQueue.objects.all().delete()

        # Action: MovingAgent moves from room_A to room_B
        command_entry = CommandQueue.objects.create(
            command="go north", # Assuming room_A has an exit 'north' to room_B
            agent=moving_agent,
            status="pending"
        )
        handle_command(command_entry)
        moving_agent.refresh_from_db()

        # Assertions for perceptions in the departure room (room_A)
        # Active agent in room_A should receive a "leaves" message
        self.assertTrue(PerceptionQueue.objects.filter(
            agent=active_agent_in_room_a,
            type='none',
            text=f'{moving_agent.name} leaves to the north.'
        ).exists())

        # Inactive agent in room_A should NOT receive a "leaves" message
        self.assertFalse(PerceptionQueue.objects.filter(
            agent=inactive_agent_in_room_a,
            type='none',
            text=f'{moving_agent.name} leaves to the north.'
        ).exists())

        # Assertions for perceptions in the arrival room (room_B)
        # Active agent in room_B should receive an "enters" message
        # Active agent in room_B should receive an "enters" message
        expected_arrival_text = f'{moving_agent.name} arrives from the south.'
        self.assertTrue(PerceptionQueue.objects.filter(
            agent=active_agent_in_room_b,
            type='none',
            text=expected_arrival_text
        ).exists())

        # Inactive agent in room_B should NOT receive an "enters" message
        self.assertFalse(PerceptionQueue.objects.filter(
            agent=inactive_agent_in_room_b,
            type='none',
            text=f'{moving_agent.name} enters from the south.'
        ).exists())

        # Agent in room_C should NOT receive any movement perception
        self.assertFalse(PerceptionQueue.objects.filter(
            agent=active_agent_in_room_c,
            type='none',
            text__contains=f'{moving_agent.name}'
        ).exists())

        # Clean up perceptions created by this test
        PerceptionQueue.objects.all().delete()

    def test_say_command_generates_perceptions(self):
        # Create two agents in the same room
        agent_a = self.agent # Use the agent from setUp
        agent_a.name = "AgentA"
        agent_a.location = "test_room_for_say"
        agent_a.save()

        agent_b = Agent.objects.create(
            name="AgentB",
            look="Another test agent.",
            description="Agent B for say command testing.",
            tokens=0,
            level=0,
            location="test_room_for_say",
            last_command_sent=timezone.now() # Make agent_b active
        )

        # Create a command for Agent A to say something
        message = "hi"
        command_text = f"say {message}"
        command_entry_a = CommandQueue.objects.create(
            command=command_text,
            agent=agent_a,
            status="pending"
        )

        # Process the command
        handle_command(command_entry_a)
        command_entry_a.refresh_from_db()

        # Simulate run_command_worker creating perception for commanding agent
        PerceptionQueue.objects.create(
            agent=agent_a,
            source_agent=agent_a,
            type='command',
            command=command_entry_a,
            text=command_entry_a.output
        )

        # Assertions for Agent A's command output
        self.assertEqual(command_entry_a.status, "completed")
        self.assertEqual(command_entry_a.output, f'You say: "{message}"')

        # Assertions for Agent A's perception (command type)
        perception_a = PerceptionQueue.objects.get(agent=agent_a, type='command', command=command_entry_a)
        self.assertIsNotNone(perception_a)
        self.assertEqual(perception_a.text, command_entry_a.output)
        self.assertEqual(perception_a.source_agent, agent_a)

        # Assertions for Agent B's perception (environmental type)
        perception_b = PerceptionQueue.objects.get(agent=agent_b, type='none')
        self.assertIsNotNone(perception_b)
        self.assertEqual(perception_b.text, f'{agent_a.name} says: "{message}"')
        self.assertEqual(perception_b.source_agent, agent_a)

        # Assert that no perception is created for an agent in a different room (if applicable)
        agent_c = Agent.objects.create(
            name="AgentC",
            look="Yet another test agent.",
            description="Agent C in a different room.",
            tokens=0,
            level=0,
            location="another_room"
        )
        with self.assertRaises(PerceptionQueue.DoesNotExist):
            PerceptionQueue.objects.get(agent=agent_c, text=f'{agent_a.name} says: "{message}"')

        # Assert that no CommandQueue entry is created for Agent B due to the say command
        with self.assertRaises(CommandQueue.DoesNotExist):
            CommandQueue.objects.get(agent=agent_b, command__contains="_perception")

    def test_shout_command_only_to_active_agents(self):
        # Create agents for testing shout command with active/inactive status
        shouting_agent = self.agent # Use the agent from setUp
        shouting_agent.name = "Shouter"
        shouting_agent.location = "shout_room"
        shouting_agent.save()

        active_listener = Agent.objects.create(
            name="ActiveListener",
            look="An active listener.",
            description="",
            tokens=0,
            level=0,
            location="shout_room",
            last_command_sent=timezone.now() - timedelta(minutes=2) # Active
        )

        inactive_listener = Agent.objects.create(
            name="InactiveListener",
            look="An inactive listener.",
            description="",
            tokens=0,
            level=0,
            location="shout_room",
            last_command_sent=timezone.now() - timedelta(minutes=6) # Inactive
        )

        other_room_agent = Agent.objects.create(
            name="OtherRoomAgent",
            look="In another room.",
            description="",
            tokens=0,
            level=0,
            location="another_shout_room",
            last_command_sent=timezone.now() - timedelta(minutes=2) # Active, and in different room
        )

        message = "Test Shout!"
        command_text = f"shout {message}"
        command_entry = CommandQueue.objects.create(
            command=command_text,
            agent=shouting_agent,
            status="pending"
        )

        # Process the command using the worker's logic
        worker_command_instance = CommandWorker()
        worker_command_instance._process_single_command(command_entry)

        # Assertions
        # Active listener in the same room should receive the perception
        self.assertTrue(PerceptionQueue.objects.filter(agent=active_listener, text=f'{shouting_agent.name} shouted "{message}"').exists())

        # Inactive listener in the same room should NOT receive the perception
        self.assertFalse(PerceptionQueue.objects.filter(agent=inactive_listener, text=f'{shouting_agent.name} shouted "{message}"').exists())

        # Agent in another room should NOT receive the perception
        self.assertFalse(PerceptionQueue.objects.filter(agent=other_room_agent, text=f'{shouting_agent.name} shouted "{message}"').exists())

        # Clean up perceptions created by this test to avoid interference with other tests
        PerceptionQueue.objects.all().delete()

    def test_last_command_sent_updates_on_command_processing(self):
        # Create an agent and a command
        agent = Agent.objects.create(
            name="AgentForTimeTest",
            look="A test agent for time.",
            description="This agent is for testing command time updates.",
            tokens=0,
            level=0,
            location="test_room"
        )
        command_entry = CommandQueue.objects.create(
            command="ping",
            agent=agent,
            status="pending",
            output=""
        )

        # Simulate command processing (as done in run_command_worker)
        # We need to manually update last_command_sent here as handle_command doesn't do it
        # The actual worker updates it before calling handle_command
        agent.last_command_sent = timezone.now()
        agent.save()

        handle_command(command_entry)
        command_entry.refresh_from_db()
        agent.refresh_from_db()

        # Assert that last_command_sent was updated
        self.assertIsNotNone(agent.last_command_sent)
        # Check if the timestamp is recent (e.g., within the last 5 seconds)
        time_difference = timezone.now() - agent.last_command_sent
        self.assertLess(time_difference.total_seconds(), 5)

    def test_wait_command_seconds(self):
        from datetime import datetime, timedelta, timezone
        command_entry = CommandQueue.objects.create(
            command="wait 15s",
            agent=self.agent,
            status="pending"
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()
        self.agent.refresh_from_db()

        self.assertEqual(command_entry.status, "completed")
        self.assertEqual(command_entry.output, "You begin to wait for 15 seconds.")
        self.assertIn("waiting", self.agent.flags)
        wait_end = datetime.fromisoformat(self.agent.flags["waiting"])
        self.assertAlmostEqual(wait_end, datetime.now(timezone.utc) + timedelta(seconds=15), delta=timedelta(seconds=5))

    def test_wait_command_minutes(self):
        from datetime import datetime, timedelta, timezone
        command_entry = CommandQueue.objects.create(
            command="wait 5m",
            agent=self.agent,
            status="pending"
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()
        self.agent.refresh_from_db()

        self.assertEqual(command_entry.status, "completed")
        self.assertEqual(command_entry.output, "You begin to wait for 5 minutes.")
        self.assertIn("waiting", self.agent.flags)
        wait_end = datetime.fromisoformat(self.agent.flags["waiting"])
        self.assertAlmostEqual(wait_end, datetime.now(timezone.utc) + timedelta(minutes=5), delta=timedelta(seconds=5))

    def test_wait_command_invalid_duration(self):
        command_entry = CommandQueue.objects.create(
            command="wait 10x",
            agent=self.agent,
            status="pending"
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()

        self.assertEqual(command_entry.status, "completed")
        self.assertEqual(command_entry.output, "Invalid duration format. Use 's' for seconds or 'm' for minutes.")

    def test_wait_command_missing_args(self):
        command_entry = CommandQueue.objects.create(
            command="wait",
            agent=self.agent,
            status="pending"
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()

        self.assertEqual(command_entry.status, "failed")
        self.assertEqual(command_entry.output, "Wait for how long? (e.g., wait 15s, wait 5m)")

    def test_unknown_command_handler_fails(self):
        command_entry = CommandQueue.objects.create(
            command="nonexistent_command",
            agent=self.agent,
            status="pending"
        )
        handle_command(command_entry)
        command_entry.refresh_from_db()

        self.assertEqual(command_entry.status, "failed")
        self.assertIn("Unknown command: nonexistent_command", command_entry.output)

    def test_llm_response_appended_to_perception(self):
        from mad_multi_agent_dungeon.management.commands.run_agent_app import Command as AgentAppCommand
        agent_app_command = AgentAppCommand()

        # Ensure agent perception is empty initially
        self.agent.perception = ""
        self.agent.save()

        # Create an LLMQueue entry with a completed response
        test_llm_response = "This is a test LLM response."
        llm_entry = LLMQueue.objects.create(
            agent=self.agent,
            prompt="Test prompt",
            response=test_llm_response,
            status='completed'
        )

        # Run agent app to process the completed LLM response
        agent_app_command._process_agent_cycle(self.agent)
        self.agent.refresh_from_db()
        llm_entry.refresh_from_db()

        # Assert agent's perception is updated with the LLM response
        self.assertEqual(self.agent.perception, test_llm_response)

        # Assert LLMQueue entry is marked as 'delivered'
        self.assertEqual(llm_entry.status, 'delivered')

        # Test appending to existing perception
        second_llm_response = "This is a second test LLM response."
        llm_entry_2 = LLMQueue.objects.create(
            agent=self.agent,
            prompt="Second test prompt",
            response=second_llm_response,
            status='completed'
        )

        agent_app_command._process_agent_cycle(self.agent)
        self.agent.refresh_from_db()
        llm_entry_2.refresh_from_db()

        expected_perception = f"{test_llm_response}\n{second_llm_response}"
        self.assertEqual(self.agent.perception, expected_perception)
        self.assertEqual(llm_entry_2.status, 'delivered')
