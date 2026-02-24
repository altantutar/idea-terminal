"""Google Gemini LLM provider via Generative Language REST API."""

from __future__ import annotations

import time

import httpx

from .base import LLMProvider


class GeminiProvider(LLMProvider):
    """Uses Gemini REST API and requests JSON responses."""

    def __init__(self, api_key: str, model: str, max_retries: int = 2) -> None:
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        # Preview models can be slower on complex prompts, so keep a generous read timeout.
        self.client = httpx.Client(timeout=httpx.Timeout(180.0))

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:"
            f"generateContent?key={self.api_key}"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 4096},
        }
        response: httpx.Response | None = None
        last_timeout: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.post(url, json=payload)
                break
            except httpx.ReadTimeout as exc:
                last_timeout = exc
                if attempt >= self.max_retries:
                    raise ValueError(
                        f"Gemini request timed out after {self.max_retries + 1} attempts."
                    ) from exc
                time.sleep(0.6 * (attempt + 1))

        if response is None:
            raise ValueError(f"Gemini request failed: {last_timeout}")

        if response.status_code >= 400:
            try:
                err = response.json()
            except ValueError:
                err = {"error": {"message": response.text}}
            message = err.get("error", {}).get("message", response.text)
            raise ValueError(f"Gemini API error ({response.status_code}): {message}")

        data = response.json()
        usage = data.get("usageMetadata", {})
        self._last_usage = {
            "input_tokens": usage.get("promptTokenCount", 0),
            "output_tokens": usage.get("candidatesTokenCount", 0),
        }

        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("Gemini API returned no candidates.")
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise ValueError("Gemini API returned empty content.")
        text: str = str(parts[0].get("text", ""))
        if not text:
            raise ValueError("Gemini API returned empty text.")
        return text
