# Deployment & Configuration

## Environment Variables
The application requires the following environment variable:
-   `HF_TOKEN`: A Hugging Face User Access Token (Read permissions). This is used to authenticate requests to the Inference API.
-   `API_URL` (Optional): Override the default HF Inference endpoint.

## Vercel vs. Cloud Run
**Important Note:** The Council deliberation process can take significant time (minutes) depending on the models and number of rounds.
-   **Vercel**: Has strict timeout limits (often 10s-60s on free tiers). The application might time out before the deliberation completes.
-   **Cloud Run / Docker**: Recommended for production. Supports long-running requests (set timeout > 300s).

## Local Development
1.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
2.  Set `HF_TOKEN` in a `.env` file or export it.
3.  Run the server:
    ```bash
    python app.py
    ```

## Docker
A `Dockerfile` is provided for containerization.
1.  Build: `docker build -t llm-council .`
2.  Run: `docker run -p 5000:5000 -e HF_TOKEN=your_token llm-council`

## Configuration (`chat/config.py`)
You can modify the council composition by editing `chat/config.py`:
```python
COUNCIL_MEMBERS = [
    "openai/gpt-oss-20b:groq",        # Model ID
    "google/gemma-3-27b-it",
    "meta-llama/Llama-3.1-8B-Instruct"
]

ARBITER_MODEL = "google/gemma-3-27b-it" # The judge
```
*Note: Ensure the models selected are available via the Hugging Face Inference API or the configured endpoint.*

