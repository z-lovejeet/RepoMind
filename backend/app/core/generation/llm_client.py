"""
RepoMind — LLM Client Module

Supports multiple LLM providers:
  - Gemini (via google-genai SDK)
  - Groq (via OpenAI-compatible SDK)

Includes automatic retry logic with exponential backoff and automatic provider fallback.

Reference:
  - Phase 6 Implementation Plan
  - Module Design → Section 7 (core/generation/llm_client.py)
"""

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Try loading .env file if available
def _load_env():
    env_paths = [
        Path(".env"),
        Path("backend/.env"),
        Path(__file__).resolve().parents[3] / "backend" / ".env",
        Path(__file__).resolve().parents[3] / ".env",
    ]
    for p in env_paths:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            os.environ.setdefault(k.strip(), v.strip().strip('"\''))
            except Exception as e:
                logger.warning(f"Failed to read {p}: {e}")

_load_env()


class LLMError(Exception):
    """Raised when LLM generation fails across all providers/retries."""
    pass


class LLMClient:
    """
    Client for calling LLM providers (Gemini and Groq).

    Usage:
        client = LLMClient(provider="groq")
        response = client.generate({"system": "...", "user": "..."})
    """

    SUPPORTED_PROVIDERS = {"gemini", "groq"}

    def __init__(
        self,
        provider: str = "groq",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        fallback_enabled: bool = True,
    ):
        """
        Initialize LLM Client.

        Args:
            provider: "groq" (default) or "gemini"
            model: Optional model override (e.g. "llama-3.1-8b-instant" or "gemini-2.0-flash")
            api_key: Optional API key override (reads from env if omitted)
            fallback_enabled: If True, fall back to secondary provider if primary fails
        """
        provider = provider.lower()
        if provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported provider '{provider}'. "
                f"Supported: {sorted(self.SUPPORTED_PROVIDERS)}"
            )

        self.provider = provider
        self.api_key = api_key
        self.fallback_enabled = fallback_enabled

        # Set default models per provider
        if model:
            self.model = model
        elif provider == "gemini":
            self.model = "gemini-2.0-flash"
        else:
            self.model = "llama-3.1-8b-instant"

    def _get_api_key(self, provider: str) -> Optional[str]:
        """Fetch API key for specified provider from self or env."""
        if provider == self.provider and self.api_key:
            return self.api_key
        if provider == "gemini":
            return os.getenv("GEMINI_API_KEY")
        if provider == "groq":
            return os.getenv("GROQ_API_KEY")
        return None

    def generate(
        self,
        prompt: Dict[str, str],
        temperature: float = 0.1,
        max_tokens: int = 2000,
        max_retries: int = 3,
    ) -> str:
        """
        Generate text response from LLM given prompt dictionary.

        Args:
            prompt: Dict containing {"system": "...", "user": "..."}
            temperature: Sampling temperature (default 0.1 for deterministic Q&A)
            max_tokens: Maximum tokens in response
            max_retries: Number of retry attempts per provider

        Returns:
            Generated answer string

        Raises:
            LLMError: If generation fails on primary and fallback providers
        """
        providers_to_try = [self.provider]
        if self.fallback_enabled:
            fallback = "gemini" if self.provider == "groq" else "groq"
            providers_to_try.append(fallback)

        errors = []

        for p in providers_to_try:
            api_key = self._get_api_key(p)
            if not api_key:
                err_msg = f"API key missing for provider '{p}' (Set {p.upper()}_API_KEY env var)"
                logger.warning(err_msg)
                errors.append(f"{p}: {err_msg}")
                continue

            try:
                return self._generate_with_retry(
                    provider=p,
                    api_key=api_key,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    max_retries=max_retries,
                )
            except Exception as e:
                logger.warning(f"Provider '{p}' failed: {e}")
                errors.append(f"{p}: {e}")

        raise LLMError(f"All LLM attempts failed. Details:\n" + "\n".join(errors))

    def _generate_with_retry(
        self,
        provider: str,
        api_key: str,
        prompt: Dict[str, str],
        temperature: float,
        max_tokens: int,
        max_retries: int,
    ) -> str:
        """Execute request with exponential backoff retry logic."""
        delay = 2.0
        for attempt in range(1, max_retries + 1):
            try:
                if provider == "groq":
                    return self._generate_groq(api_key, prompt, temperature, max_tokens)
                elif provider == "gemini":
                    return self._generate_gemini(api_key, prompt, temperature, max_tokens)
                else:
                    raise ValueError(f"Unknown provider: {provider}")
            except Exception as e:
                err_str = str(e).lower()

                # Auth errors — do not retry
                if "401" in err_str or "unauthorized" in err_str or "invalid api key" in err_str:
                    raise LLMError(f"Authentication error for {provider}: {e}") from e

                # Final attempt — re-raise
                if attempt == max_retries:
                    raise e

                logger.info(f"Attempt {attempt}/{max_retries} failed ({e}). Retrying in {delay}s...")
                time.sleep(delay)
                delay *= 2.0

        raise LLMError(f"Failed after {max_retries} attempts.")

    def _generate_groq(
        self,
        api_key: str,
        prompt: Dict[str, str],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call Groq API using OpenAI-compatible client."""
        try:
            from openai import OpenAI
        except ImportError as e:
            raise LLMError("openai package is required for Groq. Install with `pip install openai`.") from e

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )

        messages = []
        if prompt.get("system"):
            messages.append({"role": "system", "content": prompt["system"]})
        messages.append({"role": "user", "content": prompt.get("user", "")})

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if response.choices and response.choices[0].message:
            content = response.choices[0].message.content
            return content if content else ""
        return ""

    def _generate_gemini(
        self,
        api_key: str,
        prompt: Dict[str, str],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call Gemini API using google-genai SDK."""
        try:
            from google import genai
            from google.genai import types
        except ImportError as e:
            raise LLMError("google-genai package is required for Gemini. Install with `pip install google-genai`.") from e

        client = genai.Client(api_key=api_key)

        config = types.GenerateContentConfig(
            system_instruction=prompt.get("system"),
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        response = client.models.generate_content(
            model=self.model if self.provider == "gemini" else "gemini-2.0-flash",
            contents=prompt.get("user", ""),
            config=config,
        )

        if hasattr(response, "text") and response.text:
            return response.text
        return ""
