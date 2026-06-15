"""Small Gemini connectivity check used for local API validation.

This script loads the environment, creates a Gemini client, and prints a test
response so the API setup can be verified quickly.
"""

import os
import json
import time
from google import genai
from google.genai.errors import ClientError
from dotenv import load_dotenv

load_dotenv()

_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
_MODEL = "gemini-2.5-flash"  # Smoke-test model for the API connectivity check.

STRONG_MATCH = 0.40  # Match threshold placeholder kept for parity with app code.
PARTIAL_MATCH = 0.70  # Match threshold placeholder kept for parity with app code.


def _call_gemini(prompt: str) -> str:
    """Call Gemini with simple retry handling.

    Args:
        prompt: The prompt to send to Gemini.

    Returns:
        The trimmed text response.

    Side Effects:
        Retries on transient quota errors and may sleep between attempts.
    """
    for attempt in range(5):
        try:
            response = _client.models.generate_content(
                model=_MODEL,
                contents=prompt,
            )
            return response.text.strip()
        except ClientError as e:
            err = str(e)
            if ("429" in err or "503" in err) and attempt < 4:
                wait = 30 * (attempt + 1)
                print(f"API limit hit — waiting {wait}s, retry {attempt + 1}/5...")
                time.sleep(wait)
            else:
                raise


reply = _call_gemini("Say 'API is working!' if you can read this.")
print(reply)