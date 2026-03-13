#!/usr/bin/env python3
"""
Token Management for Context Window Optimization
Handles token counting, content truncation, and context window management
"""

from dataclasses import dataclass
import logging
import re
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Track token usage across different components"""

    prompt_tokens: int = 0
    sources_tokens: int = 0
    total_tokens: int = 0
    context_limit: int = 0
    usage_percentage: float = 0.0


class TokenManager:
    """Manages token counting and context window optimization"""

    def __init__(self, model_name: str = "claude-3-5-sonnet-20241022"):
        """Initialize with model-specific context limits"""
        self.model_limits = {
            "claude-sonnet-4-20250514": 200000,  # 200k tokens
            "claude-opus-4-20250514": 200000,  # 200k tokens
            "claude-haiku-4-20250514": 200000,  # 200k tokens
            "claude-3-5-sonnet-20241022": 200000,  # 200k tokens (legacy)
            "claude-3-5-haiku-20241022": 200000,  # 200k tokens (legacy)
            "claude-3-opus-20240229": 200000,  # 200k tokens (legacy)
            "gpt-4": 8192,  # 8k tokens
            "gpt-4-turbo": 128000,  # 128k tokens
            "gpt-4o": 128000,  # 128k tokens
        }

        self.model_name = model_name
        self.context_limit = self.model_limits.get(model_name, 200000)

        # Reserve tokens for response generation
        self.response_buffer = 2000
        self.available_tokens = self.context_limit - self.response_buffer

        # Content truncation settings
        self.min_source_content = 200  # Minimum chars per source
        self.max_source_content = 1000  # Maximum chars per source
        self.sources_token_limit = int(self.available_tokens * 0.6)  # 60% for sources

        logger.info(
            f"TokenManager initialized for {model_name}: {self.context_limit} tokens available"
        )

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count (approximately 1 token per 4 characters)"""
        if not text:
            return 0
        # More accurate estimation considering word boundaries and punctuation
        return int(len(text) // 3.5)  # Slightly more accurate than /4

    def optimize_sources_for_context(
        self, search_results: List[Dict], prompt_text: str
    ) -> Tuple[List[Dict], TokenUsage]:
        """Optimize sources to fit within context window"""

        prompt_tokens = self.estimate_tokens(prompt_text)
        remaining_tokens = self.available_tokens - prompt_tokens

        if remaining_tokens <= 0:
            logger.warning("Prompt too long, no room for sources")
            return [], TokenUsage(
                prompt_tokens=prompt_tokens,
                sources_tokens=0,
                total_tokens=prompt_tokens,
                context_limit=self.context_limit,
                usage_percentage=100.0,
            )

        # Allocate tokens for sources
        sources_token_budget = min(remaining_tokens, self.sources_token_limit)

        # Optimize sources
        optimized_sources = self._optimize_source_content(
            search_results, sources_token_budget
        )

        # Calculate final usage
        sources_tokens = sum(
            self.estimate_tokens(self._format_single_source(src))
            for src in optimized_sources
        )
        total_tokens = prompt_tokens + sources_tokens
        usage_percentage = (total_tokens / self.context_limit) * 100

        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            sources_tokens=sources_tokens,
            total_tokens=total_tokens,
            context_limit=self.context_limit,
            usage_percentage=usage_percentage,
        )

        logger.info(
            f"Token optimization complete: {usage.usage_percentage:.1f}% of context used"
        )

        return optimized_sources, usage

    def _optimize_source_content(
        self, search_results: List[Dict], token_budget: int
    ) -> List[Dict]:
        """Optimize source content to fit within token budget"""

        if not search_results:
            return []

        # Calculate tokens per source if distributed evenly
        tokens_per_source = token_budget // len(search_results)

        # Minimum viable sources if budget is too small
        min_sources = min(3, len(search_results))
        if tokens_per_source < 50:  # Too few tokens per source
            tokens_per_source = token_budget // min_sources
            search_results = search_results[:min_sources]

        optimized_sources = []

        for result in search_results:
            optimized_result = result.copy()

            # Get content
            content = result.get("content", result.get("raw_content", ""))

            if not content:
                continue

            # Calculate character limit based on token budget
            char_limit = min(
                tokens_per_source * 3.5,  # Convert tokens to chars
                self.max_source_content,
            )
            char_limit = max(char_limit, self.min_source_content)

            # Intelligent content truncation
            optimized_content = self._intelligently_truncate_content(
                content, int(char_limit)
            )

            optimized_result["content"] = optimized_content
            optimized_sources.append(optimized_result)

        return optimized_sources

    def _intelligently_truncate_content(self, content: str, char_limit: int) -> str:
        """Intelligently truncate content preserving important information"""

        if len(content) <= char_limit:
            return content

        # Strategy 1: Try to preserve complete sentences
        sentences = re.split(r"[.!?]+", content)
        truncated = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Check if adding this sentence would exceed limit
            potential_length = len(truncated) + len(sentence) + 1  # +1 for period

            if potential_length <= char_limit - 20:  # Leave room for "..."
                truncated += sentence + ". "
            else:
                break

        # Strategy 2: If we couldn't fit any complete sentences, use paragraph truncation
        if len(truncated.strip()) < 50:  # Very short result
            paragraphs = content.split("\n\n")
            truncated = ""

            for paragraph in paragraphs:
                paragraph = paragraph.strip()
                if not paragraph:
                    continue

                if len(truncated) + len(paragraph) <= char_limit - 20:
                    truncated += paragraph + "\n\n"
                else:
                    # Take partial paragraph
                    remaining = char_limit - len(truncated) - 3
                    if remaining > 50:
                        truncated += paragraph[:remaining] + "..."
                    break

        # Strategy 3: Simple truncation as fallback
        if len(truncated.strip()) < 50:
            truncated = content[: char_limit - 3] + "..."

        return truncated.strip()

    def _format_single_source(self, result: Dict) -> str:
        """Format a single source for token estimation"""
        title = result.get("title", "Unknown")
        content = result.get("content", result.get("raw_content", ""))
        url = result.get("url", "")

        return f"Source: {title}\nURL: {url}\nContent: {content}\n---"

    def format_optimized_sources(self, optimized_sources: List[Dict]) -> str:
        """Format optimized sources for prompt inclusion"""
        sources_text = ""

        for i, result in enumerate(optimized_sources, 1):
            title = result.get("title", "Unknown")
            content = result.get("content", result.get("raw_content", ""))
            url = result.get("url", "")

            sources_text += (
                f"\nSource {i}: {title}\nURL: {url}\nContent: {content}\n---"
            )

        return sources_text

    def get_usage_report(self, usage: TokenUsage) -> str:
        """Generate a human-readable usage report"""
        report = f"""
Token Usage Report:
- Prompt tokens: {usage.prompt_tokens:,}
- Sources tokens: {usage.sources_tokens:,}
- Total tokens: {usage.total_tokens:,}
- Context limit: {usage.context_limit:,}
- Usage: {usage.usage_percentage:.1f}%
"""

        if usage.usage_percentage > 95:
            report += (
                "\n🚨 CRITICAL: Very high token usage - likely truncation occurred"
            )
        elif usage.usage_percentage > 90:
            report += (
                "\n⚠️  WARNING: High token usage - consider reducing source content"
            )

        return report.strip()


# Convenience functions
def create_token_manager(
    model_name: str = "claude-3-5-sonnet-20241022",
) -> TokenManager:
    """Create a token manager for the specified model"""
    return TokenManager(model_name)


def estimate_content_tokens(content: str) -> int:
    """Quick token estimation for content"""
    return TokenManager("").estimate_tokens(content)
