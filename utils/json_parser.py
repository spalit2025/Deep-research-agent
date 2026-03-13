"""
Robust JSON parsing utilities
Handles various JSON formats including markdown-wrapped content
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from .observability import ComponentType, OperationType, get_logger, timed_operation

# Structured logger
logger = get_logger(ComponentType.JSON_PARSER)

# Keep fallback for compatibility
_fallback_logger = logging.getLogger(__name__)


class JSONParseError(Exception):
    """Custom exception for JSON parsing errors"""

    pass


class RobustJSONParser:
    """Robust JSON parser that handles various formats"""

    @staticmethod
    @timed_operation(
        "json_extraction", ComponentType.JSON_PARSER, OperationType.JSON_PARSING
    )
    def extract_json_from_text(text: str, expected_type: str = "any") -> Optional[Any]:
        """
        Extract JSON from text with multiple strategies

        Args:
            text: Input text that may contain JSON
            expected_type: Expected JSON type ("object", "array", "any")

        Returns:
            Parsed JSON data or None if parsing fails
        """
        context = {
            "text_length": len(text) if text else 0,
            "expected_type": expected_type,
            "text_preview": text[:100] if text else "",
        }

        logger.info("Starting JSON extraction", **context)

        if not text:
            logger.warning("Empty text provided for JSON extraction")
            return None

        # Strategy 1: Try to find JSON in markdown code blocks
        logger.debug("Trying markdown extraction strategy")
        json_data = RobustJSONParser._extract_from_markdown(text)
        if json_data is not None:
            logger.info(
                "JSON extraction successful via markdown",
                strategy="markdown",
                result_type=type(json_data).__name__,
                **context,
            )
            return json_data

        # Strategy 2: Try to find raw JSON objects/arrays
        logger.debug("Trying raw JSON extraction strategy")
        json_data = RobustJSONParser._extract_raw_json(text, expected_type)
        if json_data is not None:
            logger.info(
                "JSON extraction successful via raw parsing",
                strategy="raw_json",
                result_type=type(json_data).__name__,
                **context,
            )
            return json_data

        # Strategy 3: Try to clean and parse the entire text
        logger.debug("Trying cleaned JSON extraction strategy")
        json_data = RobustJSONParser._extract_cleaned_json(text)
        if json_data is not None:
            logger.info(
                "JSON extraction successful via cleaned parsing",
                strategy="cleaned_json",
                result_type=type(json_data).__name__,
                **context,
            )
            return json_data

        logger.warning("All JSON extraction strategies failed", **context)
        return None

    @staticmethod
    def _extract_from_markdown(text: str) -> Optional[Any]:
        """Extract JSON from markdown code blocks"""
        # Look for ```json ... ``` or ``` ... ``` blocks
        patterns = [
            r"```json\s*\n(.*?)\n```",
            r"```\s*\n(.*?)\n```",
            r"```json(.*?)```",
            r"```(.*?)```",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                json_str = match.group(1).strip()
                # Try to clean the JSON before parsing
                cleaned_json = RobustJSONParser._clean_json_string(json_str)
                try:
                    return json.loads(cleaned_json)
                except json.JSONDecodeError:
                    continue

        return None

    @staticmethod
    def _clean_json_string(json_str: str) -> str:
        """Clean JSON string by removing comments and fixing common issues"""
        # Remove single-line comments (// ...)
        lines = json_str.split("\n")
        cleaned_lines = []

        for line in lines:
            # Remove // comments but preserve // inside strings
            in_string = False
            escaped = False
            comment_start = -1

            for i, char in enumerate(line):
                if escaped:
                    escaped = False
                    continue

                if char == "\\":
                    escaped = True
                    continue

                if char == '"' and not escaped:
                    in_string = not in_string

                if not in_string and i < len(line) - 1 and line[i : i + 2] == "//":
                    comment_start = i
                    break

            if comment_start >= 0:
                line = line[:comment_start].rstrip()

            if line.strip():  # Only add non-empty lines
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    @staticmethod
    def _extract_raw_json(text: str, expected_type: str = "any") -> Optional[Any]:
        """Extract raw JSON objects or arrays"""
        if expected_type == "array" or expected_type == "any":
            # Try to find JSON arrays
            start_idx = text.find("[")
            if start_idx != -1:
                end_idx = text.rfind("]") + 1
                if end_idx > start_idx:
                    json_str = text[start_idx:end_idx]
                    cleaned_json = RobustJSONParser._clean_json_string(json_str)
                    try:
                        return json.loads(cleaned_json)
                    except json.JSONDecodeError:
                        pass

        if expected_type == "object" or expected_type == "any":
            # Try to find JSON objects
            start_idx = text.find("{")
            if start_idx != -1:
                end_idx = text.rfind("}") + 1
                if end_idx > start_idx:
                    json_str = text[start_idx:end_idx]
                    cleaned_json = RobustJSONParser._clean_json_string(json_str)
                    try:
                        return json.loads(cleaned_json)
                    except json.JSONDecodeError:
                        pass

        return None

    @staticmethod
    def _extract_cleaned_json(text: str) -> Optional[Any]:
        """Try to parse JSON after cleaning the text"""
        # Remove common non-JSON content
        cleaned = text.strip()

        # Remove leading/trailing explanatory text
        lines = cleaned.split("\n")

        # Try to find lines that look like JSON
        json_lines = []
        in_json = False

        for line in lines:
            line_stripped = line.strip()

            # Start of JSON object or array
            if line_stripped.startswith(("{", "[")):
                in_json = True
                json_lines.append(line)
            # End of JSON object or array
            elif line_stripped.endswith(("}", "]")) and in_json:
                json_lines.append(line)
                break
            # Middle of JSON
            elif in_json:
                json_lines.append(line)

        if json_lines:
            json_str = "\n".join(json_lines)
            cleaned_json = RobustJSONParser._clean_json_string(json_str)
            try:
                return json.loads(cleaned_json)
            except json.JSONDecodeError:
                pass

        return None

    @staticmethod
    def safe_parse_with_fallback(
        text: str, expected_type: str = "any", fallback_data: Any = None
    ) -> Any:
        """
        Parse JSON with fallback data if parsing fails

        Args:
            text: Input text
            expected_type: Expected JSON type
            fallback_data: Data to return if parsing fails

        Returns:
            Parsed JSON or fallback data
        """
        try:
            result = RobustJSONParser.extract_json_from_text(text, expected_type)
            if result is not None:
                return result

            logger.warning(
                "JSON parsing failed, using fallback data",
                text_length=len(text),
                expected_type=expected_type,
                fallback_provided=fallback_data is not None,
            )
            return fallback_data

        except Exception as e:
            logger.error(
                "Unexpected error in JSON parsing",
                error=e,
                text_length=len(text),
                expected_type=expected_type,
            )
            return fallback_data

    @staticmethod
    def validate_json_structure(data: Any, required_fields: List[str] = None) -> bool:
        """
        Validate that JSON data has required structure

        Args:
            data: Parsed JSON data
            required_fields: List of required field names

        Returns:
            True if structure is valid
        """
        if not isinstance(data, dict):
            return False

        if required_fields:
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                logger.warning(
                    "Missing required fields in JSON structure",
                    missing_fields=missing_fields,
                    provided_fields=list(data.keys()) if isinstance(data, dict) else [],
                    data_type=type(data).__name__,
                )
                return False

        return True


# Convenience functions
def parse_json_safely(text: str, expected_type: str = "any") -> Optional[Any]:
    """Quick function to parse JSON safely"""
    return RobustJSONParser.extract_json_from_text(text, expected_type)


def parse_report_plan(text: str) -> Optional[Dict]:
    """Parse report plan JSON with validation"""
    data = RobustJSONParser.extract_json_from_text(text, "object")
    if data and RobustJSONParser.validate_json_structure(data, ["title", "sections"]):
        # Additional validation: sections must be an array
        if not isinstance(data.get("sections"), list):
            return None
        return data
    return None


def parse_search_queries(text: str) -> Optional[List[str]]:
    """Parse search queries JSON array"""
    # First try parsing as object to properly handle {"queries": [...]} patterns
    # and reject objects with unrecognized keys
    obj_data = RobustJSONParser.extract_json_from_text(text, "object")
    if isinstance(obj_data, dict):
        # Try common keys that might contain the array
        for key in ["queries", "search_queries", "items"]:
            if key in obj_data and isinstance(obj_data[key], list):
                data = obj_data[key]
                break
        else:
            return None  # No valid array found in object
    else:
        # Fall back to direct array extraction
        data = RobustJSONParser.extract_json_from_text(text, "array")

    # Validate it's a list of strings
    if data and isinstance(data, list):
        # Check if it's empty or contains non-strings
        if len(data) == 0:
            return None
        if not all(isinstance(item, str) for item in data):
            return None
        return data

    return None
