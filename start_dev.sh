#!/bin/bash

# Start the command worker in the background
echo "Starting command worker..."
python manage.py run_command_worker &
WORKER_PID=$!

# Start the Django dev server
echo "Starting Django development server on http://127.0.0.1:8000/"
python manage.py runserver &
SERVER_PID=$!

# Start the agent application
echo "Starting agent application..."
python manage.py run_agent_app &
AGENT_APP_PID=$!

# Define a cleanup function to be called on script exit
cleanup() {
    echo -e "\nCaught signal. Shutting down background processes..."
    kill $WORKER_PID
    kill $SERVER_PID
    kill $AGENT_APP_PID
    # Wait for processes to terminate to avoid orphaned processes
    wait $WORKER_PID 2>/dev/null
    wait $SERVER_PID 2>/dev/null
    wait $AGENT_APP_PID 2>/dev/null
    echo "Shutdown complete."
    exit 0
}

# Trap common exit signals to ensure cleanup runs
trap cleanup SIGINT SIGTERM EXIT

# Wait for the primary server process. If it exits, the script will exit,
# triggering the trap. This keeps the script alive while the server is running.
wait $SERVER_PID
