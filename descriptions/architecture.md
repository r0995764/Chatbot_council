# Architecture

## Tech Stack
-   **Language**: Python 3.9+
-   **Web Framework**: Flask
-   **Frontend**: Vanilla HTML, CSS, and JavaScript.
-   **LLM Provider**: Hugging Face Inference API (via `requests`).
-   **Communication**: Server-Sent Events (SSE) for real-time streaming of the debate process.

## Project Structure

### Root
-   `app.py`: The main Flask server.
    -   `GET /`: Serves the frontend.
    -   `GET /api/config`: Returns the list of council members and the arbiter.
    -   `POST /api/convene`: The main endpoint that triggers the debate loop and streams events back to the client.

### Core Logic (`chat/`)
-   `chat/council.py`: Contains the business logic for interacting with LLMs.
    -   `query_llm`: Wrapper for HF API calls.
    -   `collect_votes`: Orchestrates the peer voting phase.
    -   `arbiter_eliminate`: Logic for the Arbiter to choose a model to eliminate.
    -   `ensemble_result`: Synthesizes the final answer.
-   `chat/config.py`: Configuration file defining `COUNCIL_MEMBERS` (list of model IDs) and `ARBITER_MODEL`.

### Frontend (`templates/`)
-   `templates/index.html`: A single-page application handling the UI.
    -   Connects to `/api/convene` and parses the SSE stream.
    -   Updates the DOM to animate avatars, show speech bubbles, and log events.

### Deployment
-   `Dockerfile`: Container definition for deploying the Python app.
-   `vercel.json`: Configuration for Vercel deployment (likely using a Python runtime adapter).

