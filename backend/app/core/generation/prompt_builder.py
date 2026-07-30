"""
RepoMind — Prompt Builder Module

Construct the LLM prompt with system instruction, retrieved context, and query.

The system prompt is the most critical piece — it contains the "grounding constraint"
that tells the LLM to answer ONLY from the provided context. Without this, the LLM
will mix its training knowledge with the context, hallucinating details that don't
exist in the user's codebase.

Prompt Structure:
    SYSTEM: You are a code analysis assistant... (grounding rules)
    USER:   CONTEXT: [retrieved chunks]
            QUESTION: [user's query]

Reference:
    - Module Design → Section 7 (core/generation/prompt_builder.py)
    - RAG Workflow → Stage 11 (Prompt Construction)
"""

import logging

logger = logging.getLogger(__name__)


class PromptBuilder:
    """
    Build LLM prompts with grounding constraints for code Q&A.

    Usage:
        builder = PromptBuilder()
        prompt = builder.build(context, query, repo_name="flask")
        # prompt = {"system": "...", "user": "..."}
    """

    # ─── System Prompt Template ───
    # This is the grounding constraint — the most important text in the system.
    SYSTEM_TEMPLATE = """You are a code analysis assistant for the repository "{repo_name}".
Answer the question based ONLY on the provided code context.

Rules:
1. Cite sources using [1], [2], etc. matching the context chunk numbers.
2. If the answer is not in the context, say "I don't have enough information in the indexed code to answer this."
3. Do NOT invent file names, function names, or line numbers.
4. Include code snippets when they help explain the answer.
5. Be concise and technical."""

    def build(
        self,
        context: str,
        query: str,
        repo_name: str = "unknown",
    ) -> dict:
        """
        Construct the full prompt for the LLM.

        Returns a provider-agnostic dict that LLMClient converts
        to the right format per provider:
            - Gemini: system_instruction= param + contents= for user
            - Groq:   [{"role": "system", ...}, {"role": "user", ...}]

        Args:
            context: Formatted context string from ContextBuilder
            query: User's natural language question
            repo_name: Name of the repository (for system prompt)

        Returns:
            {"system": "...", "user": "..."}
        """
        system_prompt = self.SYSTEM_TEMPLATE.format(repo_name=repo_name)
        user_prompt = f"CONTEXT:\n{context}\n\nQUESTION: {query}"

        total_tokens = self.estimate_tokens(system_prompt + user_prompt)
        logger.info(f"Built prompt: ~{total_tokens} tokens")

        return {
            "system": system_prompt,
            "user": user_prompt,
        }

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count without a tokenizer.

        Approximation: 1 token ≈ 4 characters.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        return len(text) // 4
