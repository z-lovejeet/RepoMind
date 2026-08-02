"""
RepoMind — LLM Client Module

Interact with LLM APIs to generate answers from retrieved context.

Supported Providers:
    - "gemini" (primary): Google Gemini via google-genai SDK
      Model: gemini-3.6-flash (free tier, excellent at code)
    - "groq" (fallback): Groq via OpenAI-compatible SDK
      Model: llama-3.1-8b-instant (free tier, blazing fast)

Key Design Decisions:
    - Auto-fallback: If Gemini fails, automatically try Groq
    - Retry with backoff: 429/500 → wait 2s → 4s → 8s (max 3 retries)
    - No retry on auth errors (401) — fail immediately
    - Temperature 0.1 for code Q&A (factual, deterministic)

Reference:
    - Module Design → Section 7 (core/generation/llm_client.py)
    - RAG Workflow → Stage 12 (LLM Generation)
"""

import logging
import os
import time
from typing import Generator

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when LLM generation fails after retries."""
    pass


class LLMClient:
    """
    Multi-provider LLM client with auto-fallback and retry logic.

    Usage:
        client = LLMClient(provider="gemini")
        answer = client.generate(
            system_prompt="You are a code analyst...",
            user_prompt="CONTEXT: ... QUESTION: How does auth work?",
        )
    """

    PROVIDERS = {"gemini", "groq"}

    def __init__(
        self,
        provider: str = "gemini",
        model: str | None = None,
        api_key: str | None = None,
        fallback_provider: str | None = "groq",
        fallback_api_key: str | None = None,
    ):
        """
        Args:
            provider: "gemini" or "groq"
            model: Model name (defaults per provider)
            api_key: API key (falls back to env var)
            fallback_provider: Auto-fallback provider (None to disable)
            fallback_api_key: Fallback API key (falls back to env var)
        """
        if provider not in self.PROVIDERS:
            raise ValueError(
                f"Unknown provider '{provider}'. Supported: {sorted(self.PROVIDERS)}"
            )

        self.provider = provider
        self.fallback_provider = fallback_provider

        # ─── Resolve API keys ───
        from app.config import settings

        if provider == "gemini":
            self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or settings.GEMINI_API_KEY
            self.model = model or os.environ.get("GEMINI_MODEL") or settings.GEMINI_MODEL
            if not self.api_key:
                raise LLMError(
                    "GEMINI_API_KEY not set. Get one at: https://aistudio.google.com/apikey"
                )
        elif provider == "groq":
            self.api_key = api_key or os.environ.get("GROQ_API_KEY") or settings.GROQ_API_KEY
            self.model = model or os.environ.get("GROQ_MODEL") or settings.GROQ_MODEL
            if not self.api_key:
                raise LLMError(
                    "GROQ_API_KEY not set. Get one at: https://console.groq.com/keys"
                )
        else:
            self.api_key = api_key
            self.model = model

        # ─── Resolve fallback ───
        if fallback_provider == "groq":
            self.fallback_api_key = fallback_api_key or os.environ.get("GROQ_API_KEY") or settings.GROQ_API_KEY
            self.fallback_model = os.environ.get("GROQ_MODEL") or settings.GROQ_MODEL
        elif fallback_provider == "gemini":
            self.fallback_api_key = fallback_api_key or os.environ.get("GEMINI_API_KEY") or settings.GEMINI_API_KEY
            self.fallback_model = os.environ.get("GEMINI_MODEL") or settings.GEMINI_MODEL
        else:
            self.fallback_api_key = None
            self.fallback_model = None

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> str:
        """
        Generate a response from the LLM.

        Tries the primary provider first. On failure, auto-falls back
        to the fallback provider.

        Args:
            system_prompt: System instruction (grounding constraints)
            user_prompt: User message (context + question)
            temperature: Randomness (0.1 = factual)
            max_tokens: Max response length

        Returns:
            Generated text string

        Raises:
            LLMError: If all providers fail
        """
        # ─── Try primary provider ───
        try:
            return self._generate_with_retry(
                provider=self.provider,
                model=self.model,
                api_key=self.api_key,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except LLMError as primary_error:
            logger.warning(f"Primary ({self.provider}) failed: {primary_error}")

            # ─── Try fallback provider ───
            if self.fallback_provider and self.fallback_api_key:
                logger.info(f"Falling back to {self.fallback_provider}...")
                try:
                    return self._generate_with_retry(
                        provider=self.fallback_provider,
                        model=self.fallback_model,
                        api_key=self.fallback_api_key,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                except LLMError as fallback_error:
                    raise LLMError(
                        f"All providers failed.\n"
                        f"  Primary ({self.provider}): {primary_error}\n"
                        f"  Fallback ({self.fallback_provider}): {fallback_error}"
                    ) from fallback_error

            raise primary_error

    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> Generator[str, None, None]:
        """
        Generate a streaming response from the LLM.

        Tries the primary provider first. On failure, logs a warning and tries
        the fallback provider. If fallback fails, falls back to non-streaming generate().
        """
        # ─── Try primary provider ───
        try:
            yield from self._generate_stream_with_provider(
                provider=self.provider,
                model=self.model,
                api_key=self.api_key,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return
        except Exception as primary_error:
            logger.warning(f"Primary stream ({self.provider}) failed: {primary_error}")

        # ─── Try fallback provider ───
        if self.fallback_provider and self.fallback_api_key:
            logger.info(f"Falling back stream to {self.fallback_provider}...")
            try:
                yield from self._generate_stream_with_provider(
                    provider=self.fallback_provider,
                    model=self.fallback_model,
                    api_key=self.fallback_api_key,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return
            except Exception as fallback_error:
                logger.warning(f"Fallback stream ({self.fallback_provider}) failed: {fallback_error}")

        # ─── Fallback to non-streaming generate() ───
        logger.info("Both streaming providers failed. Falling back to non-streaming generate().")
        yield self.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _generate_stream_with_provider(
        self,
        provider: str,
        model: str,
        api_key: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Generator[str, None, None]:
        if not api_key:
            raise LLMError(f"{provider.upper()}_API_KEY not set. Get one at: https://aistudio.google.com/apikey")
        if provider == "gemini":
            yield from self._gemini_generate_stream(
                model, api_key, system_prompt, user_prompt, temperature, max_tokens
            )
        elif provider == "groq":
            yield from self._groq_generate_stream(
                model, api_key, system_prompt, user_prompt, temperature, max_tokens
            )
        else:
            raise LLMError(f"Unsupported stream provider: {provider}")

    def _generate_with_retry(
        self,
        provider: str,
        model: str,
        api_key: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        max_retries: int = 3,
    ) -> str:
        if not api_key:
            raise LLMError(f"{provider.upper()}_API_KEY not set. Get one at: https://aistudio.google.com/apikey")
        """
        Call LLM API with exponential backoff retry.

        Retry schedule: 2s → 4s → 8s
        Retries on: 429 (rate limit), 500 (server error)
        No retry on: 401 (auth), 400 (bad request)
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                if provider == "gemini":
                    return self._gemini_generate(
                        model, api_key, system_prompt, user_prompt,
                        temperature, max_tokens,
                    )
                elif provider == "groq":
                    return self._groq_generate(
                        model, api_key, system_prompt, user_prompt,
                        temperature, max_tokens,
                    )
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # No retry on auth errors
                if "401" in error_str or "auth" in error_str or "api_key" in error_str:
                    raise LLMError(f"Auth error ({provider}): {e}") from e

                # No retry on bad request
                if "400" in error_str and "invalid" in error_str:
                    raise LLMError(f"Bad request ({provider}): {e}") from e

                # No retry on daily quota exhaustion — it won't reset for hours
                # Detected by "limit: 0" or "PerDay" in the error message
                if "limit: 0" in error_str or "perday" in error_str:
                    logger.warning(
                        f"Daily quota exhausted ({provider}). "
                        f"Skipping retries — falling back immediately."
                    )
                    raise LLMError(
                        f"Daily quota exhausted ({provider}): {e}"
                    ) from e

                # Retry on temporary rate limit (RPM) or server error
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)  # 2s, 4s, 8s
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries} failed ({provider}): {e}. "
                        f"Retrying in {wait}s..."
                    )
                    time.sleep(wait)

        raise LLMError(
            f"All {max_retries} attempts failed ({provider}): {last_error}"
        )

    def _gemini_generate(
        self,
        model: str,
        api_key: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """
        Call Gemini via google-genai SDK.

        Uses system_instruction for the grounding prompt and
        contents for the user message with context.
        """
        from google import genai

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )

        # Handle thinking models (gemini-3.x) — extract non-thought parts
        if response.candidates and response.candidates[0].content.parts:
            parts = response.candidates[0].content.parts
            output_text = "".join(
                p.text for p in parts
                if not (hasattr(p, "thought") and p.thought)
                and hasattr(p, "text") and p.text
            )
            if output_text:
                return output_text

        # Fallback to response.text
        if response.text:
            return response.text

        raise LLMError("Gemini returned empty response")

    def _gemini_generate_stream(
        self,
        model: str,
        api_key: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Generator[str, None, None]:
        from google import genai

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content_stream(
            model=model,
            contents=user_prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )

        for chunk in response:
            if chunk.candidates and chunk.candidates[0].content.parts:
                parts = chunk.candidates[0].content.parts
                for p in parts:
                    if not (hasattr(p, "thought") and p.thought) and hasattr(p, "text") and p.text:
                        yield p.text
            elif chunk.text:
                yield chunk.text

    def _groq_generate(
        self,
        model: str,
        api_key: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """
        Call Groq via OpenAI-compatible SDK.

        Groq uses the same openai package with a different base_url.
        This is the beauty of OpenAI-compatible APIs.
        """
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content
        if content:
            return content

        raise LLMError("Groq returned empty response")

    def _groq_generate_stream(
        self,
        model: str,
        api_key: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Generator[str, None, None]:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content
