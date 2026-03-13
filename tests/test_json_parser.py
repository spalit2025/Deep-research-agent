"""
Unit tests for JSON parsing functionality
Critical component that historically breaks first due to LLM output variability
"""

import json

import pytest

from utils.json_parser import RobustJSONParser, parse_report_plan, parse_search_queries


class TestRobustJSONParser:
    """Test the core JSON parsing functionality"""

    def test_extract_clean_json_object(self):
        """Test parsing clean JSON objects"""
        text = '{"title": "Test Report", "sections": []}'
        result = RobustJSONParser.extract_json_from_text(text, "object")

        assert result is not None
        assert isinstance(result, dict)
        assert result["title"] == "Test Report"
        assert result["sections"] == []

    def test_extract_clean_json_array(self):
        """Test parsing clean JSON arrays"""
        text = '["query 1", "query 2", "query 3"]'
        result = RobustJSONParser.extract_json_from_text(text, "array")

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0] == "query 1"

    def test_extract_markdown_wrapped_json(self):
        """Test parsing JSON wrapped in markdown code blocks"""
        text = """
        Here's the JSON response:

        ```json
        {
            "title": "AI in Healthcare",
            "sections": [
                {"title": "Introduction", "needs_research": false}
            ]
        }
        ```

        That should work well.
        """
        result = RobustJSONParser.extract_json_from_text(text, "object")

        assert result is not None
        assert isinstance(result, dict)
        assert result["title"] == "AI in Healthcare"
        assert len(result["sections"]) == 1

    def test_extract_markdown_no_language_tag(self):
        """Test parsing JSON in markdown without language tag"""
        text = """
        ```
        ["search query 1", "search query 2"]
        ```
        """
        result = RobustJSONParser.extract_json_from_text(text, "array")

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 2

    def test_extract_json_with_extra_text(self):
        """Test parsing when JSON is mixed with other text"""
        text = """
        I'll create the report structure:

        {"title": "Business Analysis", "sections": []}

        This should be a comprehensive report.
        """
        result = RobustJSONParser.extract_json_from_text(text, "object")

        assert result is not None
        assert result["title"] == "Business Analysis"

    def test_malformed_json_returns_none(self):
        """Test that malformed JSON returns None instead of crashing"""
        malformed_texts = [
            '{"title": "Test", "sections":}',  # Missing value
            '{"title": "Test" "sections": []}',  # Missing comma
            '{title: "Test", "sections": []}',  # Unquoted key
            '{"title": "Test", "sections": [}',  # Missing bracket
            "This is not JSON at all",
            "",  # Empty string
            "   ",  # Whitespace only
        ]

        for text in malformed_texts:
            result = RobustJSONParser.extract_json_from_text(text, "object")
            assert result is None, f"Should return None for: {text}"

    def test_json_with_special_characters(self):
        """Test JSON with special characters and unicode"""
        text = """
        ```json
        {
            "title": "Report with émojis 🚀 and quotes \\"nested\\"",
            "description": "Line 1\\nLine 2\\tTabbed",
            "unicode": "测试中文"
        }
        ```
        """
        result = RobustJSONParser.extract_json_from_text(text, "object")

        assert result is not None
        assert "🚀" in result["title"]
        assert '"nested"' in result["title"]
        assert "测试中文" in result["unicode"]

    def test_deeply_nested_json(self):
        """Test parsing deeply nested JSON structures"""
        nested_json = {
            "title": "Complex Report",
            "sections": [
                {
                    "title": "Section 1",
                    "subsections": [
                        {
                            "title": "Subsection 1.1",
                            "content": {
                                "type": "research",
                                "sources": ["url1", "url2"],
                            },
                        }
                    ],
                }
            ],
        }
        text = f"```json\n{json.dumps(nested_json)}\n```"
        result = RobustJSONParser.extract_json_from_text(text, "object")

        assert result is not None
        assert result["sections"][0]["subsections"][0]["content"]["type"] == "research"

    def test_large_json_handling(self):
        """Test handling of large JSON objects"""
        large_sections = [
            {"title": f"Section {i}", "description": "x" * 1000} for i in range(50)
        ]
        large_json = {"title": "Large Report", "sections": large_sections}
        text = json.dumps(large_json)

        result = RobustJSONParser.extract_json_from_text(text, "object")

        assert result is not None
        assert len(result["sections"]) == 50
        assert len(result["sections"][0]["description"]) == 1000

    def test_json_validation_structure(self):
        """Test JSON structure validation"""
        # Valid structure
        valid_data = {"title": "Test", "sections": []}
        assert (
            RobustJSONParser.validate_json_structure(valid_data, ["title", "sections"])
            is True
        )

        # Missing required field
        invalid_data = {"title": "Test"}
        assert (
            RobustJSONParser.validate_json_structure(
                invalid_data, ["title", "sections"]
            )
            is False
        )

        # Non-dict input
        assert (
            RobustJSONParser.validate_json_structure(["not", "a", "dict"], ["title"])
            is False
        )


class TestReportPlanParsing:
    """Test specific report plan JSON parsing"""

    def test_valid_report_plan(self):
        """Test parsing valid report plan structure"""
        plan_text = """
        ```json
        {
            "title": "AI in Healthcare Report",
            "sections": [
                {
                    "title": "Introduction",
                    "description": "Overview of AI in healthcare",
                    "needs_research": false
                },
                {
                    "title": "Current Applications",
                    "description": "Existing AI applications",
                    "needs_research": true
                }
            ]
        }
        ```
        """
        result = parse_report_plan(plan_text)

        assert result is not None
        assert result["title"] == "AI in Healthcare Report"
        assert len(result["sections"]) == 2
        assert result["sections"][0]["needs_research"] is False
        assert result["sections"][1]["needs_research"] is True

    def test_report_plan_missing_required_fields(self):
        """Test report plan with missing required fields"""
        invalid_plans = [
            '{"title": "Test"}',  # Missing sections
            '{"sections": []}',  # Missing title
            '{"title": "Test", "sections": "invalid"}',  # Invalid sections type
        ]

        for plan in invalid_plans:
            result = parse_report_plan(plan)
            assert result is None, f"Should reject plan: {plan}"

    def test_report_plan_with_extra_fields(self):
        """Test report plan with extra fields (should still work)"""
        plan_text = """
        {
            "title": "Test Report",
            "sections": [],
            "author": "AI Assistant",
            "timestamp": "2024-01-01",
            "extra_data": {"version": "1.0"}
        }
        """
        result = parse_report_plan(plan_text)

        assert result is not None
        assert result["title"] == "Test Report"
        assert "author" in result  # Extra fields preserved

    def test_report_plan_llm_response_variations(self):
        """Test various ways LLM might format the response"""
        variations = [
            # With explanation text
            """
            I'll create a report structure for you:

            ```json
            {"title": "Test Report", "sections": []}
            ```

            This structure should work well for your needs.
            """,
            # With markdown formatting
            """
            ## Report Structure

            ```json
            {"title": "Test Report", "sections": []}
            ```
            """,
            # Direct JSON response
            '{"title": "Test Report", "sections": []}',
            # JSON with comments (should handle gracefully)
            """
            {
                // This is the report title
                "title": "Test Report",
                "sections": []
            }
            """,
        ]

        for i, variation in enumerate(variations):
            result = parse_report_plan(variation)
            # All variations should now work with improved parser
            assert (
                result is not None
            ), f"Failed to parse variation {i}: {variation[:50]}..."
            assert result["title"] == "Test Report"


class TestSearchQueriesParsing:
    """Test search queries JSON parsing"""

    def test_valid_search_queries(self):
        """Test parsing valid search queries array"""
        queries_text = """
        ```json
        ["AI healthcare applications 2024", "machine learning medical diagnosis", "artificial intelligence patient care"]
        ```
        """
        result = parse_search_queries(queries_text)

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 3
        assert "2024" in result[0]

    def test_search_queries_different_formats(self):
        """Test various formats LLM might use for queries"""
        formats = [
            # Standard array
            '["query 1", "query 2", "query 3"]',
            # With markdown
            """
            ```json
            ["query 1", "query 2"]
            ```
            """,
            # Multiline array
            """
            [
                "query 1",
                "query 2",
                "query 3"
            ]
            """,
        ]

        for format_text in formats:
            result = parse_search_queries(format_text)
            assert result is not None, f"Failed to parse: {format_text}"
            assert isinstance(result, list)
            assert len(result) >= 2

    def test_search_queries_invalid_formats(self):
        """Test handling of invalid query formats"""
        invalid_formats = [
            '"single string query"',  # String instead of array
            "[]",  # Empty array
            "[123, 456]",  # Numbers instead of strings
            '{"other_field": ["query 1", "query 2"]}',  # Object without recognized query key
        ]

        for invalid in invalid_formats:
            result = parse_search_queries(invalid)
            assert result is None, f"Should reject: {invalid}"

        # Test that nested objects with query arrays ARE accepted
        valid_nested = '{"queries": ["query 1", "query 2"]}'
        result = parse_search_queries(valid_nested)
        assert result is not None, "Should accept nested object with queries key"
        assert result == ["query 1", "query 2"]

    def test_search_queries_edge_cases(self):
        """Test edge cases in search query parsing"""
        edge_cases = [
            # Very long queries
            ['["' + "x" * 500 + '", "normal query"]', 2],
            # Special characters
            ['["query with émojis 🔍", "quotes \\"test\\""]', 2],
            # Empty strings in array
            ['["valid query", "", "another valid"]', 3],
        ]

        for text, expected_len in edge_cases:
            result = parse_search_queries(text)
            assert result is not None
            assert len(result) == expected_len


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_extremely_large_input(self):
        """Test handling of extremely large input"""
        # Create a very large text input
        large_text = "x" * 100000 + '{"title": "Test", "sections": []}'

        # Should handle gracefully without crashing
        result = RobustJSONParser.extract_json_from_text(large_text, "object")
        assert result is not None or result is None  # Either works, just don't crash

    def test_binary_data_handling(self):
        """Test handling of binary data that isn't valid text"""
        binary_like = b'\x00\x01\x02{"title": "test"}\x03\x04'
        text = binary_like.decode("utf-8", errors="ignore")

        # Should handle gracefully
        RobustJSONParser.extract_json_from_text(text, "object")
        # Don't care about result, just that it doesn't crash

    def test_recursive_json_structures(self):
        """Test handling of deeply recursive structures"""
        # Create a deeply nested structure
        nested = {"level": 0}
        current = nested
        for i in range(100):
            current["next"] = {"level": i + 1}
            current = current["next"]

        text = json.dumps(nested)
        result = RobustJSONParser.extract_json_from_text(text, "object")

        assert result is not None
        assert result["level"] == 0

    @pytest.mark.parametrize("expected_type", ["object", "array", "any"])
    def test_type_expectations(self, expected_type):
        """Test that type expectations work correctly"""
        test_cases = {
            "object": '{"key": "value"}',
            "array": '["item1", "item2"]',
        }

        if expected_type in test_cases:
            text = test_cases[expected_type]
            result = RobustJSONParser.extract_json_from_text(text, expected_type)
            assert result is not None

        # "any" should accept both
        if expected_type == "any":
            for text in test_cases.values():
                result = RobustJSONParser.extract_json_from_text(text, expected_type)
                assert result is not None


# Integration tests with actual report generation scenarios
class TestIntegrationScenarios:
    """Test realistic scenarios from actual report generation"""

    def test_business_report_plan_parsing(self):
        """Test parsing a typical business report plan response"""
        business_response = """
        I'll create a comprehensive business analysis structure:

        ```json
        {
            "title": "Business Analysis: Electric Vehicle Market",
            "sections": [
                {
                    "title": "Executive Summary",
                    "description": "High-level overview and key findings",
                    "needs_research": false
                },
                {
                    "title": "Market Overview",
                    "description": "Current market size, growth, and dynamics",
                    "needs_research": true
                },
                {
                    "title": "Competitive Analysis",
                    "description": "Key players and competitive landscape",
                    "needs_research": true
                },
                {
                    "title": "Strategic Recommendations",
                    "description": "Actionable insights and next steps",
                    "needs_research": false
                }
            ]
        }
        ```

        This structure will provide a comprehensive business perspective.
        """

        result = parse_report_plan(business_response)
        assert result is not None
        assert "Electric Vehicle Market" in result["title"]
        assert len(result["sections"]) == 4
        assert any(s["title"] == "Executive Summary" for s in result["sections"])

    def test_academic_queries_parsing(self):
        """Test parsing academic-style search queries"""
        academic_response = """
        For the literature review section, I recommend these search queries:

        ```json
        [
            "machine learning healthcare literature review 2024",
            "AI medical diagnosis systematic review",
            "artificial intelligence patient outcomes research",
            "deep learning medical imaging clinical studies"
        ]
        ```

        These queries should find relevant academic sources.
        """

        result = parse_search_queries(academic_response)
        assert result is not None
        assert len(result) == 4
        assert any("literature review" in q for q in result)
        assert any("2024" in q for q in result)

    def test_recovery_from_partial_json(self):
        """Test recovery when LLM returns partially cut-off JSON"""
        # Simulate truncated response (common with token limits)
        truncated_response = """
        {
            "title": "AI Research Report",
            "sections": [
                {
                    "title": "Introduction",
                    "description": "Overview of AI developments",
                    "needs_research": false
                },
                {
                    "title": "Current Research",
                    "description": "Latest findings in"""

        # Should fail gracefully
        result = parse_report_plan(truncated_response)
        assert result is None  # Better to fail than return corrupt data
