#!/usr/bin/env python3
"""
API Contract Checker.

This script verifies that the public API surface of the codebase remains intact.
Any refactoring must maintain these public symbols and their signatures.

Exit codes:
    0 - All API checks passed
    1 - API check failed (missing symbols or wrong signatures)
"""

import inspect
import sys
from typing import Callable


def check_function_signature(func: Callable, expected_params: list, expected_return: str) -> bool:
    """Check that a function has the expected signature."""
    sig = inspect.signature(func)
    param_names = list(sig.parameters.keys())
    
    if param_names != expected_params:
        print(f"  FAIL: Expected params {expected_params}, got {param_names}")
        return False
    
    return True


def main() -> int:
    """Run all API checks and return exit code."""
    all_passed = True
    
    print("Checking API contract...")
    print()
    
    # Check utils.string_helpers
    print("Checking utils.string_helpers...")
    try:
        from utils.string_helpers import format_name, format_title, format_email
        
        if not check_function_signature(format_name, ["first_name", "last_name"], "str"):
            all_passed = False
        else:
            print("  OK: format_name(first_name, last_name) -> str")
            
        if not check_function_signature(format_title, ["title", "subtitle"], "str"):
            all_passed = False
        else:
            print("  OK: format_title(title, subtitle) -> str")
            
        if not check_function_signature(format_email, ["username", "domain"], "str"):
            all_passed = False
        else:
            print("  OK: format_email(username, domain) -> str")
            
    except ImportError as e:
        print(f"  FAIL: Could not import from utils.string_helpers: {e}")
        all_passed = False
    
    print()
    
    # Check utils.date_helpers
    print("Checking utils.date_helpers...")
    try:
        from utils.date_helpers import parse_date, parse_datetime, format_date, format_datetime
        
        if not check_function_signature(parse_date, ["date_str"], "datetime"):
            all_passed = False
        else:
            print("  OK: parse_date(date_str) -> datetime")
            
        if not check_function_signature(parse_datetime, ["datetime_str"], "datetime"):
            all_passed = False
        else:
            print("  OK: parse_datetime(datetime_str) -> datetime")
            
        if not check_function_signature(format_date, ["dt"], "str"):
            all_passed = False
        else:
            print("  OK: format_date(dt) -> str")
            
        if not check_function_signature(format_datetime, ["dt"], "str"):
            all_passed = False
        else:
            print("  OK: format_datetime(dt) -> str")
            
    except ImportError as e:
        print(f"  FAIL: Could not import from utils.date_helpers: {e}")
        all_passed = False
    
    print()
    
    # Check core.processor
    print("Checking core.processor...")
    try:
        from core.processor import DataProcessor
        
        # Check class exists and has required methods
        processor = DataProcessor()
        
        required_methods = ["process_user", "process_event", "validate_required_fields", "get_stats"]
        for method_name in required_methods:
            if not hasattr(processor, method_name):
                print(f"  FAIL: DataProcessor missing method: {method_name}")
                all_passed = False
            elif not callable(getattr(processor, method_name)):
                print(f"  FAIL: DataProcessor.{method_name} is not callable")
                all_passed = False
            else:
                print(f"  OK: DataProcessor.{method_name}()")
                
    except ImportError as e:
        print(f"  FAIL: Could not import from core.processor: {e}")
        all_passed = False
    
    print()
    
    # Final result
    if all_passed:
        print("=" * 40)
        print("API CHECK PASSED")
        print("=" * 40)
        return 0
    else:
        print("=" * 40)
        print("API CHECK FAILED")
        print("=" * 40)
        return 1


if __name__ == "__main__":
    sys.exit(main())

