import os
import time
from google import genai
from google.genai.errors import ClientError
from dotenv import load_dotenv

load_dotenv()

_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
_status_callback = None
_cache: dict[str, list[float]] = {}


def embed(text: str) -> list[float]:
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text.")

    # Return cached embedding if we already embedded this text
    if text in _cache:
        return _cache[text]

    for attempt in range(5):
        try:
            response = _client.models.embed_content(
                model="gemini-embedding-001",
                contents=text,
            )
            vector = response.embeddings[0].values
            _cache[text] = vector
            return vector
        except ClientError as e:
            err = str(e)
            if ("429" in err or "503" in err) and attempt < 4:
                wait = 30 * (attempt + 1)
                msg = f"API limit hit — waiting {wait}s, retry {attempt + 1}/5..."
                print(msg)
                if _status_callback:
                    _status_callback(msg)
                time.sleep(wait)
            else:
                raise


def clear_cache() -> None:
    _cache.clear()