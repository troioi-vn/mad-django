# Project Features and Implementation Summary

This document summarizes the features and implementation details of the `mad-django` project, developed with a Test-Driven Development (TDD) approach.

## Project Setup and Core Models

*   **Django Project Initialization**: A new Django project named `mad_django` was created.
*   **Django App Creation**: A Django app named `mad_multi_agent_dungeon` was created and registered in `INSTALLED_APPS`.
*   **Git Repository Setup**: A Git repository was initialized, and user name/email were configured.
*   **`Agent` Model**:
    *   Created with fields: `name` (unique ID), `look` (short description), `description` (text), `flags` (JSONField, optional), `inventory` (JSONField, optional), `tokens` (integer), `level` (integer), `location` (string for `room_id`), `last_command_sent` (DateTimeField, optional), `last_retrieved` (DateTimeField, optional), `prompt` (TextField, optional), `perception` (TextField, optional), `perception_limit` (integer, default 5000), and `memoriesLoaded` (JSONField, optional, storing a list of memory IDs).
    *   Includes `__str__` method for readable representation.
    *   Includes an `is_active` method that returns `True` if the agent's `last_command_sent` was less than 5 minutes ago, otherwise `False`.
*   **`CommandQueue` Model**:
    *   Created to manage commands for agents.
    *   Fields include: `command` (string), `agent` (ForeignKey to `Agent`), `status` (choices: `pending`, `processing`, `completed`, `delivered`, `failed`), `date` (automatically set on creation), and `output` (text, optional).
    *   Includes `__str__` method for readable representation.
*   **`PerceptionQueue` Model**:
    *   Created to manage perceptions for agents, acting as the new input queue for agent processing.
    *   Fields include: `agent` (ForeignKey to `Agent`, the recipient of the perception), `source_agent` (ForeignKey to `Agent`, the initiator of the action causing the perception, nullable), `type` (choices: `command`, `none`; indicates if the perception is a direct command response or an environmental event), `command` (ForeignKey to `CommandQueue`, links to the originating command, nullable), `text` (TextField, the content of the perception), `delivered` (boolean, indicates if the agent has processed this perception), and `date` (automatically set on creation).
    *   Includes `__str__` method for readable representation.
*   **`requirements.txt`**: A `requirements.txt` file was created, initially listing `Django==5.2.3`.
*   **`LLMAPIKey` Model**:
    *   Created to store and manage API keys for Large Language Models.
    *   Fields include: `key` (unique string), `is_active` (boolean), `created_at` (datetime), `last_used` (datetime), `description` (text), and `parameters` (JSONField for API-specific settings).
    *   Includes `__str__` method for readable representation.
*   **`llm_api.py` Module**:
    *   A new module created to encapsulate the logic for interacting with LLM APIs.
    *   Contains `call_gemini_api` function for making API calls to the Google Gemini API.

## Test-Driven Development (TDD) Approach

*   All new features (models, command handlers) were developed using a TDD cycle:
    1.  Write a failing test.
    2.  Implement the minimum code to make the test pass.
    3.  Refactor if necessary.

## Command Handling and Worker

*   **Command Handler System**:
    *   A `commands.py` module was created to centralize command handling logic.
    *   Uses a dictionary (`COMMAND_HANDLERS`) to map command names to their respective handler functions, allowing for easy extension.
    *   A generic `handle_command` function dispatches commands to the appropriate handler.
*   A `go_wrapper` function was created to handle directional aliases for the `go` command.

## Implemented Commands

*   **`ping`**: Responds with "pong". Used for testing the connection.
*   **`look`**: Shows the title and description of the agent's current room, including only *active* agents present. (Alias `l` removed from documentation as its test was removed)
*   **`go <direction>`**: Moves the agent in the specified direction (e.g., `go north`). Notifies *active* agents in the old room of the agent's departure and *active* agents in the new room of the agent's arrival.
*   **`north` / `n`**: Alias for `go north`.
*   **`south` / `s`**: Alias for `go south`.
*   **`east` / `e`**: Alias for `go east`.
*   **`west` / `w`**: Alias for `go west`.
*   **`up` / `u`**: Alias for `go up`.
*   **`down` / `d`**: Alias for `go down`.
*   **`inventory`**: Displays the items in the agent's inventory.
*   **`examine <object>`**: Examines an object in the room.
*   **`where`**: Shows the agent's current location (room ID and title).
*   **`shout <message>`**: Sends a message to all other *active* agents in the world.
*   **`say <message>`**: Sends a message to all other agents in the same room.
*   **`use <object>`**: Uses an object in the room.
*   **`help`**: Lists all available commands.
*   **`score`**: Displays the agent's current stats (name, level, tokens, location).
*   **`meditate <duration>`**: The agent meditates for a specified duration (e.g., `meditate 5m`).
*   **`memory-create <key> <value>`**: Creates a new memory with the specified key and value.
*   **`memory-update <key> <new_value>`**: Updates the value of an existing memory.
*   **`memory-append <key> <text_to_append>`**: Appends text to the value of an existing memory.
*   **`memory-remove <key>`**: Removes a memory.
*   **`memory-list`**: Lists all memories for the agent.
*   **`memory-load <key>`**: Adds the ID of the specified memory to the agent's `memoriesLoaded` list.
*   **`memory-unload <key>`**: Removes the ID of the specified memory from the agent's `memoriesLoaded` list.

## Command and Perception Queue Workers

*   **Command Queue Worker**:
    *   Implemented as a Django management command (`python manage.py run_command_worker`).
    *   Continuously polls the `CommandQueue` for `pending` commands.
    *   Sets the command status to `processing`, calls the appropriate handler, and updates the command's status and output.
    *   **Crucially, after processing a command, it updates the `last_command_sent` timestamp on the associated `Agent` and creates relevant entries in the `PerceptionQueue` for the commanding agent (type `command`) and for other *active* agents in the same room (type `none`, for environmental perceptions like shouts and says).**
*   **Perception Queue Worker (Agent Application)**:
    *   The agent application (`python manage.py run_agent_app <agent_name>`) now continuously polls the `PerceptionQueue` for undelivered perceptions specific to that agent.
    *   If the agent is in the 'thinking' phase, it checks for a 'completed' entry in the `LLMQueue`.
        *   If a completed LLM response is found, commands embedded within the LLM response (e.g., `[command|say|hi]`, `[memory|load|key]`) are extracted and a new entry is created in the `CommandQueue` for each. The *original* content of the LLM response is then appended to the agent's `perception` field.
        *   The `LLMQueue` entry is then marked as 'delivered', and the agent's `phase` is changed to 'acting'.
        *   If no completed LLM response is found, and there are no `pending` or `thinking` LLM requests for the agent, the agent will consolidate its prompt (base prompt + loaded memories + perception) and create a new entry in the `LLMQueue`, setting its phase to 'thinking'.
        *   If no completed LLM response is found, but there are `pending` or `thinking` LLM requests, the agent continues to wait in the 'thinking' phase.
    *   If the agent is not in the 'thinking' phase, it processes perceptions from the `PerceptionQueue` by simply appending their text to the agent's `perception` field. It does *not* extract or execute commands from the perception text.
    *   After processing all perceptions for the current cycle, it constructs a comprehensive prompt for the LLM by concatenating the agent's `prompt` field, the values of all memories whose IDs are in `agent.memoriesLoaded`, and the text of the last processed perception. The perception text is truncated to the agent's `perception_limit`.
    *   This combined prompt is then used to create a new entry in the `LLMQueue`, and the agent's `phase` is set to 'thinking'.
    *   Finally, it marks the perception as `delivered`.

## Django Admin Integration

*   **Model Registration**: `Agent`, `CommandQueue`, `PerceptionQueue`, and `Memory` models are registered with the Django admin, providing a default interface for managing instances.
*   **Custom Admin Site**:
    *   A custom `MyAdminSite` was created to extend Django's default admin functionality.
    *   This custom site is used to register the `Agent`, `CommandQueue`, and `PerceptionQueue` models.
*   **"Send Command to Queue" Page**:
    *   A custom admin page (`/admin/send_command/`) was created to allow users to select an `Agent` and send a `command` to the `CommandQueue`.
    *   Uses a Django `Form` (`SendCommandForm`) for input.
    *   Integrates with the Django messages framework to provide feedback on command submission.
    *   Accessible via a link on the main Django admin index page.
*   **Dynamic Command Log**:
    *   The "Send Command to Queue" admin page now includes a real-time, dynamically updating log of recent **perceptions** and their outputs.
    *   Fetches data from a new API endpoint (`/admin/command_log_api/`) using JavaScript.
    *   Displays `Agent_name > command 
 output` (for command perceptions) or the formatted `text` directly (for environmental perceptions like 'say' messages, which are now pre-formatted in the backend) in a log-style format. The API now conditionally includes `command_id` and `command_text` only for `command` type perceptions.

## Agent Visualization

*   **Agent Detail Page**:
    *   A new page at `/agent/<agent_name>/` provides a real-time dashboard of an agent's state.
    *   The page is dynamically updated every few seconds using JavaScript and a new API endpoint.
    *   The dashboard displays:
        *   **Vitals**: Status, phase, location, level, tokens, and activity timestamps.
        *   **Prompt Composition**: A tabbed view of the final, base, and perception prompts.
        *   **Loaded Memories**: A table of the agent's loaded memories.
        *   **Activity Feeds**: Recent commands, perceptions, and the latest LLM queue entry.
*   **Admin Integration**:
    *   The `Agent` list in the Django admin now includes a direct link to each agent's detail page.
*   **Main Page Update**:
    *   The main page of the application (`/`) now displays a list of all agents, with links to their respective detail pages.
*   **Reset Agent Functionality**:
    *   The "Reset" button on the agent detail page now clears the agent's `perception` field.
    *   It also marks all `pending` and `thinking` LLM requests for that agent as `failed`.
*   **Reset Agent Memory Functionality**:
    *   A "Reset Memory" button has been added to the agent detail page.
    *   This clears all memories associated with the agent and empties the `memoriesLoaded` list.

## How to Run

1.  **Create a Superuser**: If you haven't already, run `python manage.py createsuperuser` in your terminal.
2.  **Start the Development Server**: Run `python manage.py runserver`.

3.  **Access Admin**: Go to `http://127.0.0.1:8000/admin/` in your browser.
4.  **Start the Worker**: In a separate terminal, run `python manage.py run_command_worker` to process commands.

Use start_dev.sh to start the server and worker together:
```bash
./start_dev.sh
``` 

## Development Pipeline: Test-Driven Development (TDD) Approach

The development process for this project strictly adhered to a Test-Driven Development (TDD) methodology. This iterative and cyclical approach ensures that features are built with a strong foundation of testing, leading to more robust and maintainable code.

**The TDD Cycle (Red-Green-Refactor):**

1.  **Red (Write a Failing Test):**
    *   Before writing any new functional code, a unit test is written for the specific feature or functionality to be implemented.
    *   This test is designed to fail initially because the corresponding code does not yet exist or does not behave as expected.
    *   The failure confirms that the test is correctly identifying the absence or incorrectness of the feature.

2.  **Green (Write Minimum Code to Pass the Test):**
    *   Only after a test has failed, the minimum amount of code necessary to make that specific test pass is written.
    *   The focus here is solely on passing the test, not on perfect design or comprehensive implementation. This often results in simple, sometimes even "ugly," code.

3.  **Refactor (Improve Code Quality):**
    *   Once the test passes (the "green" stage), the code is refactored. This involves improving the design, structure, readability, and efficiency of the newly written code without changing its external behavior (i.e., without breaking the tests).
    *   Refactoring steps might include:
        *   Removing duplication.
        *   Improving naming conventions.
        *   Breaking down large functions or classes.
        *   Optimizing algorithms (if performance is a concern and tests still pass).
    *   After refactoring, all tests are run again to ensure that no existing functionality has been inadvertently broken.

**Key Principles Applied:**

*   **"Fail First"**: Every new feature begins with a failing test, providing clear confirmation of what needs to be built.
*   **Small Steps**: Features are broken down into the smallest possible testable units, allowing for rapid iteration and immediate feedback.
*   **Safety Net**: The growing suite of automated tests acts as a safety net, allowing for confident refactoring and future development without fear of introducing regressions.
*   **Clear Requirements**: Writing tests first forces a clear understanding of the requirements and expected behavior of the code.

**Application in this Project:**

This pipeline was applied to:

*   **Model Creation**: Tests were written to assert the creation and properties of `Agent` and `CommandQueue` instances before their models were defined.
*   **Field Additions/Modifications**: Tests were updated to reflect new fields (e.g., `location` for `Agent`) before the model was altered.
*   **Command Handling Logic**: Tests were created for specific command handlers (e.g., `ping`) to verify their output and status changes before the handler functions were implemented.
*   **Admin Views**: While not strictly TDD for the UI, the underlying models and logic supporting the admin views were developed with TDD.

This systematic approach ensures that each component of the application is thoroughly tested and functions as intended, contributing to a stable and maintainable codebase.

## Project Architecture

The agent creates its prompt and puts it into the LLM queue.
The worker loops over the LLM queue and processes requests (sending requests to the LLM API).
The agent receives a response from the LLM queue and processes it by managing memories and running commands via the commands queue.
The worker also loops over the commands queue and processes commands from the agent. It then puts responses into the perception queue.
The agent also loops over the perception queue and appends it to the perception part of the agent's prompt.

The agent's prompt consists of the prompt base (from the file in the prompts directory), loaded memories, and perception (recycled text, 5,000 symbols long).

## Essential Development Commands

To ensure a smooth development workflow and maintain code quality, the following commands are frequently used in this project:

*   **Install/Synchronize Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    This command installs all necessary Python packages listed in `requirements.txt`. It should be run whenever `requirements.txt` is updated.

*   **Apply Database Migrations**:
    ```bash
    python manage.py migrate
    ```
    This command applies any pending database schema changes. It's crucial to run this after making modifications to Django models.

*   **Run Tests**:
    ```bash
    python manage.py test
    ```
    Executes the entire test suite for the project. This is a core part of our TDD workflow and should be run frequently to ensure code correctness.

*   **Code Formatting (Black)**:
    ```bash
    black .
    ```
    Automatically formats Python code to adhere to the Black style guide. Run this before committing changes to maintain consistent code style.

*   **Linting (Ruff)**:
    ```bash
    ruff check .
    ```
    Checks Python code for style violations and potential errors using Ruff. This helps enforce code quality and identify issues early.

## Future Enhancements and Features
Gemini! When you take a task from this list, don't be shy to ask questions for clarification. If you see that there are better methods instead of the proposed solution - offer to discuss them.

### Logs principles:
Log What Matters — Errors, warnings, and important events. Skip noise.
Use Proper Levels — DEBUG, INFO, WARNING, ERROR, CRITICAL.
No Sensitive Data — Never log passwords, tokens, or personal info.
Structure Logs — Use module-based loggers (__name__).
Readable or Parsable

### TODO list (concrete tasks):


(Gemini! Before answering, please rephrase the user's request. Keep in mind that he is learning English and would be grateful for pointing out mistakes or rephrase options. Don't be shy about using technical jargon and DevOps vocabulary. Meow!)