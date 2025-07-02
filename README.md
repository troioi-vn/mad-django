# Multi-Agent Dungeon (MAD)

## Project Overview

The Multi-Agent Dungeon (MAD) is a text-based, multi-agent environment built with Django. It serves as a dynamic space where digital constructs, referred to as "Agents," exist and interact. The project emphasizes a robust, queue-based system for agent communication and command processing, enabling complex interactions within the dungeon. 

## Project Architecture

The MAD project operates on a  queue-based architecture designed for asynchronous agent interaction and processing:

1.  **Agent Prompt Generation**: An agent constructs its prompt, which comprises:
    *   **Foundation**: Basic information about the agent and its purpose (e.g., from `prompts/Mad.md`).
    *   **Memory**: Key-value pairs of information loaded into the agent's context.
    *   **Perception**: Processed information, including responses from MAD and LLM-generated content.
    This consolidated prompt is then submitted to the `LLMQueue`.

2.  **LLM Queue Worker**: A dedicated worker continuously monitors the `LLMQueue`. It processes requests by sending the agent's prompt to an external Large Language Model (LLM) API (currently a placeholder).

3.  **Agent LLM Response Processing**: Upon receiving a response from the `LLMQueue`, the agent processes it. This involves:
    *   Managing its internal memories based on the LLM's output.
    *   Extracting and executing commands embedded within the LLM response by submitting them to the `CommandQueue`.

4.  **Command Queue Worker**: Another worker continuously processes commands from the `CommandQueue`. After executing a command, it generates relevant responses and environmental observations, which are then placed into the `PerceptionQueue`.

5.  **Agent Perception Integration**: The agent continuously monitors the `PerceptionQueue` for new perceptions. Any new perceptions are appended to the agent's `perception` field, which then feeds back into the next prompt generation cycle.

This cyclical flow of prompt generation, LLM interaction, command execution, and perception integration allows agents to maintain context, react to their environment, and interact dynamically within the dungeon.

### Perception Mechanism

The `Perception` section of an agent's prompt is crucial for its continuous learning and interaction. When the LLM generates a response, it's processed and added to this section. If the LLM's output contains embedded commands (e.g., `[command|look]`), these are executed by MAD. The results of these commands replace the original command tags in the `Perception` section, providing the agent with updated environmental feedback. For example:

*   **LLM Output**: `"I decide to look around [command|look]"`
*   **After MAD Processing**: `"I decide to look around processed_command_look
You are in Haven. Exits: down"`

### Memory Management

Memory is a vital component of an agent's prompt, allowing it to store and retrieve information as key-value pairs.

*   **Key**: A unique, meaningful identifier for the memory.
*   **Value**: Any text content the agent needs to remember.

Agents can interact with their memories using specific commands:

*   `[command|memory-create|key|value]`: Creates a new memory.
*   `[command|memory-append|key|additional text]`: Appends text to an existing memory.
*   `[command|memory-update|key|new value]`: Replaces an existing memory's value.
*   `[command|memory-load|key]`: Includes a memory's value in the agent's prompt.
*   `[command|memory-unload|key]`: Removes a memory's value from the agent's prompt.

Successful memory commands are also reflected in the `Perception` section, e.g., `processed_command_memory-create_key_value`.

## Getting Started

Follow these steps to set up and run the Multi-Agent Dungeon project locally.

### Prerequisites

*   Python 3.x
*   pip (Python package installer)

### Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/your-repo/mad-django.git
    cd mad-django
    ```
    (Note: Replace `https://github.com/your-repo/mad-django.git` with the actual repository URL.)

2.  **Create and activate a virtual environment**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Apply database migrations**:
    ```bash
    python manage.py migrate
    ```

5.  **Create a superuser** (for accessing the Django Admin):
    ```bash
    python manage.py createsuperuser
    ```
    Follow the prompts to create your admin user.

### Running the Application

To run the MAD application, you need to start both the Django development server and the command worker.

1.  **Start the Development Server**:
    ```bash
    python manage.py runserver
    ```
    This will typically start the server at `http://127.0.0.1:8000/`.

2.  **Start the Command Worker**:
    In a **separate terminal**, run:
    ```bash
    python manage.py run_command_worker
    ```
    This worker processes commands submitted to the `CommandQueue`.

3.  **Start the Agent Application**:
    In another **separate terminal**, you can run an agent:
    ```bash
    python manage.py run_agent_app <agent_name>
    ```
    Replace `<agent_name>` with the name of an agent you've created (e.g., "Mad").

Alternatively, you can use the provided convenience script to start the server and worker together:

```bash
./start_dev.sh
```

### Accessing the Admin Interface and Agent Dashboard

*   **Django Admin**: Navigate to `http://127.0.0.1:8000/admin/` in your web browser. Log in with the superuser credentials you created. From here, you can manage agents, send commands, and monitor queues.
*   **Agent Detail Page**: Access an agent's real-time dashboard at `http://127.0.0.1:8000/agent/<agent_name>/`.