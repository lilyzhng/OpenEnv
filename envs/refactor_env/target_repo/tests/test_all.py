"""Tests for the target repo - these must pass after any refactoring."""

import pytest
from datetime import datetime

# Import from utils
from utils.string_helpers import format_name, format_title, format_email
from utils.date_helpers import parse_date, parse_datetime, format_date, format_datetime

# Import from core
from core.processor import DataProcessor


class TestStringHelpers:
    """Tests for string formatting utilities."""
    
    def test_format_name_both_parts(self):
        assert format_name("john", "doe") == "John Doe"
        
    def test_format_name_first_only(self):
        assert format_name("john", "") == "John"
        
    def test_format_name_last_only(self):
        assert format_name("", "doe") == "Doe"
        
    def test_format_name_empty(self):
        assert format_name("", "") == ""
        
    def test_format_name_with_whitespace(self):
        assert format_name("  john  ", "  doe  ") == "John Doe"
        
    def test_format_name_none_values(self):
        assert format_name(None, None) == ""
        
    def test_format_title_with_subtitle(self):
        assert format_title("hello", "world") == "Hello: World"
        
    def test_format_title_without_subtitle(self):
        assert format_title("hello", "") == "Hello"
        
    def test_format_title_empty(self):
        assert format_title("", "") == ""
        
    def test_format_email_valid(self):
        assert format_email("John.Doe", "Example.COM") == "john.doe@example.com"
        
    def test_format_email_missing_parts(self):
        assert format_email("john", "") == ""
        assert format_email("", "example.com") == ""


class TestDateHelpers:
    """Tests for date parsing and formatting utilities."""
    
    def test_parse_date_valid(self):
        result = parse_date("2024-01-15")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        
    def test_parse_date_with_whitespace(self):
        result = parse_date("  2024-01-15  ")
        assert result.year == 2024
        
    def test_parse_date_invalid(self):
        with pytest.raises(ValueError):
            parse_date("invalid")
            
    def test_parse_date_empty(self):
        with pytest.raises(ValueError):
            parse_date("")
            
    def test_parse_date_none(self):
        with pytest.raises(ValueError):
            parse_date(None)
            
    def test_parse_datetime_valid(self):
        result = parse_datetime("2024-01-15 10:30:45")
        assert result.year == 2024
        assert result.hour == 10
        assert result.minute == 30
        
    def test_parse_datetime_invalid(self):
        with pytest.raises(ValueError):
            parse_datetime("2024-01-15")  # Missing time
            
    def test_format_date(self):
        dt = datetime(2024, 1, 15, 10, 30, 45)
        assert format_date(dt) == "2024-01-15"
        
    def test_format_datetime(self):
        dt = datetime(2024, 1, 15, 10, 30, 45)
        assert format_datetime(dt) == "2024-01-15 10:30:45"
        
    def test_format_date_none(self):
        with pytest.raises(ValueError):
            format_date(None)


class TestDataProcessor:
    """Tests for the data processor."""
    
    def test_process_user_full_data(self):
        processor = DataProcessor()
        data = {
            "first_name": "john",
            "last_name": "doe",
            "email_user": "John.Doe",
            "email_domain": "Example.COM",
            "birth_date": "1990-05-15",
        }
        result = processor.process_user(data)
        
        assert result["full_name"] == "John Doe"
        assert result["email"] == "john.doe@example.com"
        assert result["birth_date"] == "1990-05-15"
        
    def test_process_user_missing_fields(self):
        processor = DataProcessor()
        data = {}
        result = processor.process_user(data)
        
        assert result["full_name"] == ""
        assert result["email"] == ""
        assert result["birth_date"] is None
        
    def test_process_user_increments_count(self):
        processor = DataProcessor()
        processor.process_user({})
        processor.process_user({})
        
        stats = processor.get_stats()
        assert stats["processed"] == 2
        
    def test_process_event_full_data(self):
        processor = DataProcessor()
        data = {
            "title": "annual meeting",
            "subtitle": "planning session",
            "event_time": "2024-06-15 14:00:00",
        }
        result = processor.process_event(data)
        
        assert result["display_title"] == "Annual Meeting: Planning Session"
        assert result["event_time"] == "2024-06-15 14:00:00"
        
    def test_process_event_missing_subtitle(self):
        processor = DataProcessor()
        data = {"title": "meeting"}
        result = processor.process_event(data)
        
        assert result["display_title"] == "Meeting"
        
    def test_validate_required_fields_all_present(self):
        processor = DataProcessor()
        data = {"name": "John", "email": "john@example.com"}
        
        assert processor.validate_required_fields(data, ["name", "email"]) is True
        
    def test_validate_required_fields_missing(self):
        processor = DataProcessor()
        data = {"name": "John"}
        
        assert processor.validate_required_fields(data, ["name", "email"]) is False
        
    def test_validate_required_fields_empty_string(self):
        processor = DataProcessor()
        data = {"name": "John", "email": "  "}
        
        assert processor.validate_required_fields(data, ["name", "email"]) is False
        
    def test_error_count_incremented(self):
        processor = DataProcessor()
        processor.validate_required_fields({}, ["required_field"])
        
        stats = processor.get_stats()
        assert stats["errors"] == 1

