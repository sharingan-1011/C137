from openai import AsyncOpenAI
from backend.config import BASE_URL, API_KEY


def get_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=f"{BASE_URL}/v1",
        api_key=API_KEY,
    )
