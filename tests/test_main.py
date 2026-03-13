"""
Unit tests for main.py CLI
Validates argparse configuration and argument parsing
"""

import pytest

from main import VALID_TEMPLATES, build_parser


class TestBuildParser:
    """Test CLI argument parser configuration"""

    def test_parser_exists(self):
        """build_parser should return an ArgumentParser"""
        parser = build_parser()
        assert parser is not None

    def test_no_args_gives_none_topic(self):
        """No arguments should result in topic=None (interactive mode)"""
        parser = build_parser()
        args = parser.parse_args([])
        assert args.topic is None
        assert args.template == "standard"

    def test_topic_positional_arg(self):
        """Topic should be parsed as positional argument"""
        parser = build_parser()
        args = parser.parse_args(["AI in Healthcare"])
        assert args.topic == "AI in Healthcare"

    def test_template_short_flag(self):
        """Template should be settable via -t flag"""
        parser = build_parser()
        args = parser.parse_args(["Topic", "-t", "business"])
        assert args.template == "business"

    def test_template_long_flag(self):
        """Template should be settable via --template flag"""
        parser = build_parser()
        args = parser.parse_args(["Topic", "--template", "academic"])
        assert args.template == "academic"

    def test_all_valid_templates_accepted(self):
        """All valid templates should be accepted"""
        parser = build_parser()
        for tmpl in VALID_TEMPLATES:
            args = parser.parse_args(["Topic", "-t", tmpl])
            assert args.template == tmpl

    def test_invalid_template_rejected(self):
        """Invalid template should cause argparse error"""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["Topic", "-t", "invalid_template"])

    def test_template_default_is_standard(self):
        """Default template should be 'standard'"""
        parser = build_parser()
        args = parser.parse_args(["Topic"])
        assert args.template == "standard"

    def test_help_flag_exits(self):
        """--help should trigger SystemExit"""
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])
        assert exc_info.value.code == 0


class TestValidTemplates:
    """Test the VALID_TEMPLATES constant"""

    def test_all_templates_present(self):
        """All expected templates should be in VALID_TEMPLATES"""
        expected = {"standard", "business", "academic", "technical", "quick"}
        assert set(VALID_TEMPLATES) == expected

    def test_templates_is_list(self):
        """VALID_TEMPLATES should be a list"""
        assert isinstance(VALID_TEMPLATES, list)
