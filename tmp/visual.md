### Agent Detail Page Design

This feature will be a new, read-only web page for each agent, accessible via a URL like `/agent/<agent_name>/`. The page will be designed as a dashboard, automatically refreshing every few seconds to provide a live view of the agent's status.

**Page Layout:**

The page will be divided into several sections:

1.  **Header:**
    *   **Agent Name:** Prominently displayed.
    *   **Status Badge:** A color-coded badge indicating the agent's current `phase` (e.g., "Thinking", "Acting") and `is_active` status.

2.  **Core Vitals (Main Panel):**
    *   **Location:** The agent's current room ID.
    *   **Level & Tokens:** Current level and token count.
    *   **Last Activity:** Timestamps for `last_command_sent` and `last_retrieved`.

3.  **Prompt Composition (Tabbed View):**
    *   **Tab 1: Final Prompt:** A text area showing the fully constructed prompt ready to be sent to the LLM.
    *   **Tab 2: Base Prompt:** The static, initial prompt loaded from the agent's prompt file.
    *   **Tab 3: Perception Buffer:** The recent perceptions that feed into the prompt.

4.  **Loaded Memories:**
    *   A list or table displaying the `key` and `value` of each memory currently in the agent's `memoriesLoaded` list.

5.  **Activity Feeds (Side Panel):**
    *   **Recent Commands:** A log of the last 5 commands sent by the agent from the `CommandQueue`, showing the command and its status (`pending`, `completed`, etc.).
    *   **Recent Perceptions:** A log of the last 5 perceptions received by the agent from the `PerceptionQueue`.
    *   **LLM Queue:** The latest entry for this agent from the `LLMQueue`, showing the status (`pending`, `completed`) and the final response.

### Technical Implementation Plan

1.  **Create New URL Routes:**
    *   Add a URL in `mad_multi_agent_dungeon/urls.py` for the agent detail page: `path('agent/<str:agent_name>/', views.agent_detail_view, name='agent_detail')`.
    *   Add a corresponding API endpoint to serve the dynamic data: `path('api/agent/<str:agent_name>/', views.agent_detail_api, name='agent_detail_api')`.

2.  **Develop View Functions:**
    *   In `mad_multi_agent_dungeon/views.py`, create `agent_detail_view` to render the main HTML template.
    *   Create `agent_detail_api` to query the database for all the necessary agent data and return it as a JSON object.

3.  **Build the HTML Template:**
    *   Create a new template `mad_multi_agent_dungeon/templates/mad_multi_agent_dungeon/agent_detail.html`.
    *   Structure the HTML and add basic CSS for a clean, readable dashboard layout.

4.  **Implement Dynamic Updates:**
    *   Add JavaScript to the template that uses the `fetch` API to call the `/api/agent/<agent_name>/` endpoint every 3-5 seconds.
    *   The script will then parse the JSON response and dynamically update the content of the various sections on the page.

5.  **Add Navigation:**
    *   I will modify the Django admin's `Agent` list view to include a direct link to the new detail page for each agent, making it easily accessible.
