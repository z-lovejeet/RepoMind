"""
RepoMind — Prompt Builder Module

Assembles grounding system instructions and user query context into a
structured prompt dictionary for the LLM.

Grounding Constraint:
    The system prompt strictly instructs the LLM to answer ONLY from the
    provided code context and cite sources using [1], [2] matching the
    context chunk numbers. This prevents hallucinations and ungrounded claims.

Reference:
    - Phase 6 Implementation Plan
    - Module Design → Section 7 (core/generation/prompt_builder.py)
    - RAG Workflow → Stage 11 (Prompt Construction)
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class PromptBuilder:
    """
    Construct system and user messages for LLM generation.

    Usage:
        builder = PromptBuilder()
        prompt = builder.build(context="...", query="How does auth work?", repo_name="flask")
    """

    SYSTEM_TEMPLATE = (
        "You are a code analysis assistant for the repository \"{repo_name}\".\n"
        "Answer the user's question based ONLY on the provided code context.\n\n"
        "Rules:\n"
        "1. Cite sources using [1], [2], etc. matching the context chunk numbers.\n"
        "2. If the answer is not in the context, say \"I don't have enough information in the indexed code to answer this.\"\n"
        "3. Do NOT invent file names, function names, or line numbers.\n"
        "4. Include code snippets when they help explain the answer.\n"
        "5. Be concise, technical, and accurate."
    )

    def build(
        self,
        context: str,
        query: str,
        repo_name: str = "repository",
    ) -> Dict[str, str]:
        """
        Construct prompt dictionary with system and user roles.

        Args:
            context: Formatted context string from ContextBuilder
            query: User's question
            repo_name: Optional name of the repository being queried

        Returns:
            Dict with "system" and "user" prompt strings
        """
        system_instruction = self.SYSTEM_TEMPLATE.format(
            repo_name=repo_name if repo_name else "repository"
        )

        user_content = (
            f"CONTEXT:\n"
            f"{context}\n\n"
            f"QUESTION: {query}"
        )

        logger.debug(
            f"Built prompt for query '{query}': "
            f"~{self.estimate_tokens(user_content)} user tokens"
        )

        return {
            "system": system_instruction,
            "user": user_content,
        }

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count of a string (1 token ≈ 4 characters).

        Args:
            text: Input string

        Returns:
            Estimated token count
        """
        return len(text) // 4
