import asyncio
import anthropic
import json
import logging
from config import settings

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.model = "claude-sonnet-4-6"
        if self.provider == "anthropic":
            self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def complete(self, system_prompt: str, user_content: str, max_tokens: int = 4096) -> str:
        if self.provider == "anthropic":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )
            return response.content[0].text
        raise ValueError(f"Unsupported LLM provider: {self.provider}")

    async def complete_with_retry(
        self,
        system_prompt: str,
        user_content: str,
        max_tokens: int = 2048,
        max_retries: int = 3,
    ) -> str:
        """complete() with exponential backoff on rate limit errors."""
        for attempt in range(max_retries):
            try:
                return await self.complete(system_prompt, user_content, max_tokens)
            except anthropic.RateLimitError:
                if attempt == max_retries - 1:
                    raise
                wait = (2 ** attempt) * 5  # 5s, 10s, 20s
                logger.warning(f"Rate limit hit, waiting {wait}s before retry {attempt + 1}/{max_retries}")
                await asyncio.sleep(wait)
        raise RuntimeError("complete_with_retry exhausted retries")

    async def complete_json(self, system_prompt: str, user_content: str, max_tokens: int = 4096) -> dict:
        """Complete and parse JSON response, retrying once on parse failure."""
        text = await self.complete(system_prompt, user_content, max_tokens)
        try:
            return _parse_json(text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed: {e}. Retrying with stricter instruction.")
            retry_content = (
                f"{user_content}\n\n"
                "IMPORTANT: Your previous response was not valid JSON. "
                "Return ONLY valid JSON — no markdown, no explanation, no preamble."
            )
            text2 = await self.complete(system_prompt, retry_content, max_tokens)
            return _parse_json(text2)

    async def complete_json_with_retry(
        self,
        system_prompt: str,
        user_content: str,
        max_tokens: int = 2048,
        max_retries: int = 3,
    ) -> dict:
        """complete_json() with rate-limit retry. Use this for all classification calls."""
        for attempt in range(max_retries):
            try:
                text = await self.complete(system_prompt, user_content, max_tokens)
                try:
                    return _parse_json(text)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parse failed: {e}. Retrying parse.")
                    retry_content = (
                        f"{user_content}\n\n"
                        "IMPORTANT: Your previous response was not valid JSON. "
                        "Return ONLY valid JSON — no markdown, no explanation, no preamble."
                    )
                    text2 = await self.complete(system_prompt, retry_content, max_tokens)
                    return _parse_json(text2)
            except anthropic.RateLimitError:
                if attempt == max_retries - 1:
                    raise
                wait = (2 ** attempt) * 5
                logger.warning(f"Rate limit hit, waiting {wait}s (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait)
        raise RuntimeError("complete_json_with_retry exhausted retries")


def _parse_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    return json.loads(cleaned)


llm = LLMService()
