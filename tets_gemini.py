import os
import json
import time
from google import genai
from google.genai.errors import ClientError
from dotenv import load_dotenv

load_dotenv()

_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
_MODEL = "gemini-2.5-flash"

STRONG_MATCH = 0.40
PARTIAL_MATCH = 0.70


def _call_gemini(prompt: str) -> str:
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