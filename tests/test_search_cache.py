"""
Unit tests for search cache module
Validates JSON serialization (replaces insecure pickle) and cache behavior
"""

import json
import os
import tempfile

from utils.search_cache import CacheEntry, SearchCache


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

            # Verify .json file was created, not .pkl
            files = os.listdir(tmpdir)
            json_files = [f for f in files if f.endswith(".json")]
            pkl_files = [f for f in files if f.endswith(".pkl")]

            assert len(json_files) == 1
            assert len(pkl_files) == 0

            # Verify the file is valid JSON
            with open(os.path.join(tmpdir, json_files[0]), "r") as f:
                data = json.load(f)
            assert data["query"] == "test query"
            assert data["topic"] == "testing"

    def test_load_from_disk_reads_json(self):
        """Cache should load entries from .json files on initialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a cache and save an entry
            cache1 = SearchCache(cache_dir=tmpdir, enable_file_cache=True)
            cache1.cache_results(
                query="persistent query",
                results=[{"title": "Result", "url": "https://example.com"}],
                topic="topic",
                section_type="default",
            )

            # Create a new cache from the same directory
            cache2 = SearchCache(cache_dir=tmpdir, enable_file_cache=True)
            result = cache2.get_cached_results("persistent query", "topic")

            assert result is not None
            assert len(result) == 1
            assert result[0]["title"] == "Result"

    def test_cleanup_legacy_pkl_files(self):
        """Legacy .pkl files should be removed on init"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake .pkl file
            pkl_path = os.path.join(tmpdir, "legacy_entry.pkl")
            with open(pkl_path, "wb") as f:
                f.write(b"fake pickle data")

            assert os.path.exists(pkl_path)

            # Initialize cache - should clean up .pkl files
            SearchCache(cache_dir=tmpdir, enable_file_cache=True)

            assert not os.path.exists(pkl_path)


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
