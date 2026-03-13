#!/usr/bin/env python3
"""
Search Result Caching System
Intelligent caching of search results with query similarity detection
"""

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A single cache entry with metadata"""

    query: str
    results: List[Dict[str, Any]]
    timestamp: float
    topic: str
    section_type: str
    hit_count: int = 0

    def is_expired(self, ttl_hours: float) -> bool:
        """Check if cache entry is expired"""
        return time.time() - self.timestamp > (ttl_hours * 3600)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class CacheStats:
    """Cache performance statistics"""

    total_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_saved_queries: int = 0
    cache_size: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate percentage"""
        return (
            (self.cache_hits / self.total_queries * 100)
            if self.total_queries > 0
            else 0.0
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary for reporting"""
        return {
            "total_queries": self.total_queries,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": f"{self.hit_rate:.1f}%",
            "total_saved_queries": self.total_saved_queries,
            "cache_size": self.cache_size,
        }


class SearchCache:
    """Intelligent search result caching system"""

    def __init__(
        self,
        cache_dir: str = "cache",
        ttl_hours: float = 24.0,
        max_cache_size: int = 1000,
        similarity_threshold: float = 0.75,
        enable_file_cache: bool = True,
    ):
        """
        Initialize the search cache

        Args:
            cache_dir: Directory for file-based cache storage
            ttl_hours: Time-to-live for cache entries in hours
            max_cache_size: Maximum number of entries to keep in memory
            similarity_threshold: Minimum similarity score for cache hits
            enable_file_cache: Whether to persist cache to disk
        """
        self.cache_dir = cache_dir
        self.ttl_hours = ttl_hours
        self.max_cache_size = max_cache_size
        self.similarity_threshold = similarity_threshold
        self.enable_file_cache = enable_file_cache

        # In-memory cache
        self.memory_cache: Dict[str, CacheEntry] = {}

        # Performance statistics
        self.stats = CacheStats()

        # Create cache directory
        if self.enable_file_cache:
            os.makedirs(cache_dir, exist_ok=True)
            self._cleanup_legacy_pkl_files()
            self._load_cache_from_disk()

        logger.info(
            f"SearchCache initialized: TTL={ttl_hours}h, Max size={max_cache_size}"
        )

    def _generate_cache_key(self, query: str, topic: str = "") -> str:
        """Generate a cache key for a query"""
        # Normalize query for better matching
        normalized_query = query.lower().strip()
        cache_string = f"{normalized_query}:{topic.lower().strip()}"
        return hashlib.md5(cache_string.encode()).hexdigest()

    def _calculate_query_similarity(self, query1: str, query2: str) -> float:
        """Calculate similarity between two queries"""
        # Normalize queries
        q1 = query1.lower().strip()
        q2 = query2.lower().strip()

        # Direct match
        if q1 == q2:
            return 1.0

        # Sequence matching
        seq_similarity = SequenceMatcher(None, q1, q2).ratio()

        # Keyword overlap
        words1 = set(q1.split())
        words2 = set(q2.split())
        if words1 or words2:
            overlap = len(words1 & words2)
            union = len(words1 | words2)
            keyword_similarity = overlap / union if union > 0 else 0.0
        else:
            keyword_similarity = 0.0

        # Combined similarity (weighted average)
        combined_similarity = (seq_similarity * 0.6) + (keyword_similarity * 0.4)

        return combined_similarity

    def _find_similar_cached_query(
        self, query: str, topic: str = ""
    ) -> Optional[CacheEntry]:
        """Find a similar cached query that can be reused"""
        best_match = None
        best_similarity = 0.0

        for entry in self.memory_cache.values():
            # Check if entry is expired
            if entry.is_expired(self.ttl_hours):
                continue

            # Calculate similarity
            similarity = self._calculate_query_similarity(query, entry.query)

            # Consider topic relevance
            if topic and entry.topic:
                topic_similarity = self._calculate_query_similarity(topic, entry.topic)
                # Boost similarity if topics are related
                if topic_similarity > 0.3:
                    similarity += topic_similarity * 0.2

            # Check if this is the best match so far
            if similarity > best_similarity and similarity >= self.similarity_threshold:
                best_similarity = similarity
                best_match = entry

        return best_match

    def get_cached_results(
        self,
        query: str,
        topic: str = "",
        section_type: str = "",  # noqa: ARG002
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached results for a query

        Args:
            query: The search query
            topic: The overall report topic
            section_type: The type of section being researched

        Returns:
            Cached results if found, None otherwise
        """
        self.stats.total_queries += 1

        # First, try exact cache key match
        cache_key = self._generate_cache_key(query, topic)

        if cache_key in self.memory_cache:
            entry = self.memory_cache[cache_key]
            if not entry.is_expired(self.ttl_hours):
                entry.hit_count += 1
                self.stats.cache_hits += 1
                logger.debug(f"Cache HIT (exact): {query[:50]}...")
                return entry.results
            else:
                # Remove expired entry
                del self.memory_cache[cache_key]

        # Try to find similar cached query
        similar_entry = self._find_similar_cached_query(query, topic)
        if similar_entry:
            similar_entry.hit_count += 1
            self.stats.cache_hits += 1
            logger.debug(
                f"Cache HIT (similar): {query[:50]}... -> {similar_entry.query[:50]}..."
            )
            return similar_entry.results

        # No cache hit
        self.stats.cache_misses += 1
        logger.debug(f"Cache MISS: {query[:50]}...")
        return None

    def cache_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
        topic: str = "",
        section_type: str = "",
    ) -> None:
        """
        Cache search results

        Args:
            query: The search query
            results: The search results to cache
            topic: The overall report topic
            section_type: The type of section being researched
        """
        if not results:
            return

        cache_key = self._generate_cache_key(query, topic)

        # Create cache entry
        entry = CacheEntry(
            query=query,
            results=results,
            timestamp=time.time(),
            topic=topic,
            section_type=section_type,
            hit_count=0,
        )

        # Add to memory cache
        self.memory_cache[cache_key] = entry

        # Enforce cache size limit
        if len(self.memory_cache) > self.max_cache_size:
            self._evict_least_used()

        # Save to disk if enabled
        if self.enable_file_cache:
            self._save_entry_to_disk(cache_key, entry)

        # Update statistics
        self.stats.cache_size = len(self.memory_cache)

        logger.debug(f"Cached results for: {query[:50]}...")

    def _evict_least_used(self) -> None:
        """Evict least recently used entries when cache is full"""
        # Sort entries by hit count and timestamp
        sorted_entries = sorted(
            self.memory_cache.items(), key=lambda x: (x[1].hit_count, x[1].timestamp)
        )

        # Remove oldest 10% of entries
        num_to_remove = max(1, len(sorted_entries) // 10)

        for i in range(num_to_remove):
            cache_key, entry = sorted_entries[i]
            del self.memory_cache[cache_key]
            logger.debug(f"Evicted cache entry: {entry.query[:50]}...")

    def _save_entry_to_disk(self, cache_key: str, entry: CacheEntry) -> None:
        """Save a cache entry to disk as JSON"""
        try:
            file_path = os.path.join(self.cache_dir, f"{cache_key}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(entry.to_dict(), f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save cache entry to disk: {e}")

    def _load_cache_from_disk(self) -> None:
        """Load cache entries from disk"""
        if not os.path.exists(self.cache_dir):
            return

        loaded_count = 0
        for filename in os.listdir(self.cache_dir):
            if filename.endswith(".json"):
                try:
                    file_path = os.path.join(self.cache_dir, filename)
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    entry = CacheEntry(**data)

                    # Check if entry is expired
                    if not entry.is_expired(self.ttl_hours):
                        cache_key = filename[:-5]  # Remove .json extension
                        self.memory_cache[cache_key] = entry
                        loaded_count += 1
                    else:
                        # Remove expired file
                        os.remove(file_path)

                except Exception as e:
                    logger.warning(f"Failed to load cache entry {filename}: {e}")

        self.stats.cache_size = len(self.memory_cache)
        logger.info(f"Loaded {loaded_count} cache entries from disk")

    def _cleanup_legacy_pkl_files(self) -> None:
        """Remove legacy pickle cache files (security: pickle allows arbitrary code execution)"""
        if not os.path.exists(self.cache_dir):
            return
        removed = 0
        for filename in os.listdir(self.cache_dir):
            if filename.endswith(".pkl"):
                os.remove(os.path.join(self.cache_dir, filename))
                removed += 1
        if removed:
            logger.info(f"Removed {removed} legacy pickle cache files")

    def clear_cache(self) -> None:
        """Clear all cache entries"""
        self.memory_cache.clear()

        # Clear disk cache
        if self.enable_file_cache and os.path.exists(self.cache_dir):
            for filename in os.listdir(self.cache_dir):
                if filename.endswith(".json"):
                    os.remove(os.path.join(self.cache_dir, filename))

        # Reset statistics
        self.stats = CacheStats()
        logger.info("Cache cleared")

    def clear_expired_entries(self) -> int:
        """Clear expired cache entries and return count of removed entries"""
        expired_keys = []

        for cache_key, entry in self.memory_cache.items():
            if entry.is_expired(self.ttl_hours):
                expired_keys.append(cache_key)

        # Remove expired entries
        for cache_key in expired_keys:
            del self.memory_cache[cache_key]

            # Remove from disk
            if self.enable_file_cache:
                file_path = os.path.join(self.cache_dir, f"{cache_key}.json")
                if os.path.exists(file_path):
                    os.remove(file_path)

        self.stats.cache_size = len(self.memory_cache)
        logger.info(f"Removed {len(expired_keys)} expired cache entries")

        return len(expired_keys)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        return self.stats.to_dict()

    def get_cache_report(self) -> str:
        """Get a formatted cache performance report"""
        stats = self.get_cache_stats()

        report = f"""
Search Cache Performance Report:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Total Queries: {stats['total_queries']:,}
• Cache Hits: {stats['cache_hits']:,}
• Cache Misses: {stats['cache_misses']:,}
• Hit Rate: {stats['hit_rate']}
• Current Cache Size: {stats['cache_size']:,} entries
• Estimated Queries Saved: {stats['total_saved_queries']:,}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        if stats["cache_hits"] > 0:
            report += "\n✅ Cache is providing significant performance improvements!"
            report += f"\n💰 Estimated API calls saved: {stats['cache_hits']:,}"
        else:
            report += "\n💡 Cache is warming up - performance improvements will increase over time."

        return report.strip()


# Factory function for creating cache instances
def create_search_cache(config: Dict[str, Any]) -> SearchCache:
    """Create a search cache instance with configuration"""
    return SearchCache(
        cache_dir=config.get("cache_dir", "cache"),
        ttl_hours=config.get("cache_ttl_hours", 24.0),
        max_cache_size=config.get("max_cache_size", 1000),
        similarity_threshold=config.get("similarity_threshold", 0.75),
        enable_file_cache=config.get("enable_file_cache", True),
    )
