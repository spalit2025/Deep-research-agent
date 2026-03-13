"""
Unit tests for search cache module
Validates JSON serialization, similarity matching, expiration, eviction, and stats
"""

import json
import os
import tempfile
import time

from utils.search_cache import CacheEntry, CacheStats, SearchCache, create_search_cache


class TestSearchCacheJSONSerialization:
    """Test JSON-based cache persistence (replacing pickle)"""

    def test_save_and_load_uses_json(self):
        """Cache entries must be saved as .json files, not .pkl"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = SearchCache(cache_dir=tmpdir, enable_file_cache=True)

            cache.cache_results(
                query="test query",
                results=[{"title": "Test", "url": "https://example.com"}],
                topic="testing",
                section_type="default",
            )

            files = os.listdir(tmpdir)
            json_files = [f for f in files if f.endswith(".json")]
            pkl_files = [f for f in files if f.endswith(".pkl")]

            assert len(json_files) == 1
            assert len(pkl_files) == 0

            with open(os.path.join(tmpdir, json_files[0]), "r") as f:
                data = json.load(f)
            assert data["query"] == "test query"
            assert data["topic"] == "testing"

    def test_load_from_disk_reads_json(self):
        """Cache should load entries from .json files on initialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache1 = SearchCache(cache_dir=tmpdir, enable_file_cache=True)
            cache1.cache_results(
                query="persistent query",
                results=[{"title": "Result", "url": "https://example.com"}],
                topic="topic",
                section_type="default",
            )

            cache2 = SearchCache(cache_dir=tmpdir, enable_file_cache=True)
            result = cache2.get_cached_results("persistent query", "topic")

            assert result is not None
            assert len(result) == 1
            assert result[0]["title"] == "Result"

    def test_cleanup_legacy_pkl_files(self):
        """Legacy .pkl files should be removed on init"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkl_path = os.path.join(tmpdir, "legacy_entry.pkl")
            with open(pkl_path, "wb") as f:
                f.write(b"fake pickle data")

            assert os.path.exists(pkl_path)
            SearchCache(cache_dir=tmpdir, enable_file_cache=True)
            assert not os.path.exists(pkl_path)

    def test_corrupted_json_file_skipped(self):
        """Corrupted JSON files should be skipped without crashing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_path = os.path.join(tmpdir, "corrupted.json")
            with open(bad_path, "w") as f:
                f.write("{invalid json content")

            # Should not raise
            cache = SearchCache(cache_dir=tmpdir, enable_file_cache=True)
            assert len(cache.memory_cache) == 0


class TestSearchCacheBehavior:
    """Test core cache behavior"""

    def test_cache_hit_exact_match(self):
        """Exact query match should return cached results"""
        cache = SearchCache(enable_file_cache=False)
        results = [{"title": "Test", "url": "https://example.com"}]

        cache.cache_results("test query", results, "topic")
        cached = cache.get_cached_results("test query", "topic")

        assert cached is not None
        assert cached == results

    def test_cache_miss(self):
        """Non-matching query should return None"""
        cache = SearchCache(enable_file_cache=False)
        result = cache.get_cached_results("nonexistent query")
        assert result is None

    def test_empty_results_not_cached(self):
        """Empty results should not be cached"""
        cache = SearchCache(enable_file_cache=False)
        cache.cache_results("query", [], "topic")
        assert len(cache.memory_cache) == 0

    def test_cache_hit_increments_hit_count(self):
        """Cache hits should increment the hit counter"""
        cache = SearchCache(enable_file_cache=False)
        results = [{"title": "Test"}]

        cache.cache_results("test query", results, "topic")
        cache.get_cached_results("test query", "topic")
        cache.get_cached_results("test query", "topic")

        assert cache.stats.cache_hits == 2
        assert cache.stats.total_queries == 2

    def test_cache_miss_increments_miss_count(self):
        """Cache misses should increment the miss counter"""
        cache = SearchCache(enable_file_cache=False)
        cache.get_cached_results("no match")

        assert cache.stats.cache_misses == 1
        assert cache.stats.total_queries == 1


class TestSimilarityMatching:
    """Test fuzzy query similarity matching"""

    def test_similar_query_returns_cached(self):
        """Very similar queries should return cached results"""
        cache = SearchCache(enable_file_cache=False, similarity_threshold=0.7)
        results = [{"title": "AI Result"}]

        cache.cache_results("artificial intelligence trends 2024", results)
        cached = cache.get_cached_results("artificial intelligence trends 2025")

        # These are similar enough to match
        assert cached is not None

    def test_dissimilar_query_returns_none(self):
        """Very different queries should not match"""
        cache = SearchCache(enable_file_cache=False, similarity_threshold=0.75)
        results = [{"title": "AI Result"}]

        cache.cache_results("artificial intelligence trends", results)
        cached = cache.get_cached_results("quantum computing hardware")

        assert cached is None

    def test_case_insensitive_matching(self):
        """Cache matching should be case-insensitive"""
        cache = SearchCache(enable_file_cache=False)
        results = [{"title": "Test"}]

        cache.cache_results("Machine Learning", results, "topic")
        cached = cache.get_cached_results("machine learning", "topic")

        assert cached is not None


class TestCacheExpiration:
    """Test cache TTL and expiration"""

    def test_expired_entry_returns_none(self):
        """Expired entries should not be returned"""
        cache = SearchCache(enable_file_cache=False, ttl_hours=0.0001)
        results = [{"title": "Old"}]

        cache.cache_results("query", results, "topic")
        time.sleep(0.5)  # Wait for expiration

        cached = cache.get_cached_results("query", "topic")
        assert cached is None

    def test_non_expired_entry_returned(self):
        """Non-expired entries should be returned"""
        cache = SearchCache(enable_file_cache=False, ttl_hours=24.0)
        results = [{"title": "Fresh"}]

        cache.cache_results("query", results, "topic")
        cached = cache.get_cached_results("query", "topic")

        assert cached is not None

    def test_clear_expired_entries(self):
        """clear_expired_entries should remove only expired entries"""
        cache = SearchCache(enable_file_cache=False, ttl_hours=0.0001)

        cache.cache_results("old", [{"title": "Old"}], "topic")
        time.sleep(0.5)

        removed = cache.clear_expired_entries()
        assert removed == 1
        assert len(cache.memory_cache) == 0


class TestCacheEviction:
    """Test cache size limits and eviction"""

    def test_eviction_on_max_size(self):
        """Cache should evict entries when max size is exceeded"""
        cache = SearchCache(enable_file_cache=False, max_cache_size=3)

        for i in range(5):
            cache.cache_results(
                f"query {i}", [{"title": f"Result {i}"}], f"topic {i}"
            )

        # Should have evicted some entries
        assert len(cache.memory_cache) <= 3


class TestCacheClear:
    """Test cache clearing"""

    def test_clear_cache_empties_memory(self):
        """clear_cache should remove all entries from memory"""
        cache = SearchCache(enable_file_cache=False)
        cache.cache_results("q1", [{"title": "R1"}])
        cache.cache_results("q2", [{"title": "R2"}])

        cache.clear_cache()

        assert len(cache.memory_cache) == 0
        assert cache.stats.total_queries == 0

    def test_clear_cache_removes_disk_files(self):
        """clear_cache should remove all .json files from disk"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = SearchCache(cache_dir=tmpdir, enable_file_cache=True)
            cache.cache_results("q1", [{"title": "R1"}])

            cache.clear_cache()

            json_files = [f for f in os.listdir(tmpdir) if f.endswith(".json")]
            assert len(json_files) == 0


class TestCacheStats:
    """Test cache statistics and reporting"""

    def test_cache_stats_to_dict(self):
        """CacheStats.to_dict should return all fields"""
        stats = CacheStats(total_queries=10, cache_hits=7, cache_misses=3)
        d = stats.to_dict()

        assert d["total_queries"] == 10
        assert d["cache_hits"] == 7
        assert d["cache_misses"] == 3
        assert d["hit_rate"] == "70.0%"

    def test_hit_rate_zero_queries(self):
        """Hit rate should be 0.0 when no queries have been made"""
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_get_cache_stats(self):
        """get_cache_stats should return current stats"""
        cache = SearchCache(enable_file_cache=False)
        cache.cache_results("q", [{"title": "R"}])
        cache.get_cached_results("q")
        cache.get_cached_results("miss")

        stats = cache.get_cache_stats()
        assert stats["total_queries"] == 2
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 1

    def test_get_cache_report(self):
        """get_cache_report should return formatted string"""
        cache = SearchCache(enable_file_cache=False)
        cache.cache_results("q", [{"title": "R"}])
        cache.get_cached_results("q")

        report = cache.get_cache_report()
        assert "Cache" in report
        assert "Hit" in report


class TestCacheEntry:
    """Test CacheEntry dataclass"""

    def test_is_expired(self):
        """is_expired should detect expired entries"""
        entry = CacheEntry(
            query="test",
            results=[],
            timestamp=time.time() - 7200,  # 2 hours ago
            topic="topic",
            section_type="default",
        )
        assert entry.is_expired(1.0)  # 1 hour TTL
        assert not entry.is_expired(3.0)  # 3 hour TTL

    def test_to_dict(self):
        """to_dict should return serializable dictionary"""
        entry = CacheEntry(
            query="test",
            results=[{"title": "R"}],
            timestamp=123.0,
            topic="topic",
            section_type="default",
        )
        d = entry.to_dict()
        assert d["query"] == "test"
        assert d["timestamp"] == 123.0
        # Should be JSON-serializable
        json.dumps(d)


class TestCreateSearchCache:
    """Test factory function"""

    def test_create_from_config(self):
        """create_search_cache should configure from dict"""
        config = {
            "cache_ttl_hours": 12.0,
            "max_cache_size": 500,
            "similarity_threshold": 0.8,
            "enable_file_cache": False,
        }
        cache = create_search_cache(config)
        assert cache.ttl_hours == 12.0
        assert cache.max_cache_size == 500
        assert cache.similarity_threshold == 0.8

    def test_create_with_defaults(self):
        """create_search_cache should use defaults for missing keys"""
        cache = create_search_cache({})
        assert cache.ttl_hours == 24.0
        assert cache.max_cache_size == 1000
