"""Date parsing and formatting utilities with obvious duplication."""

from datetime import datetime


def parse_date(date_str: str) -> datetime:
    """Parse a date string in YYYY-MM-DD format.
    
    Args:
        date_str: Date string to parse
        
    Returns:
        Parsed datetime object
        
    Raises:
        ValueError: If date string is invalid
    """
    # Validate input
    if date_str is None:
        raise ValueError("Date string cannot be None")
    
    # Strip whitespace
    date_str = date_str.strip()
    
    # Check for empty string
    if not date_str:
        raise ValueError("Date string cannot be empty")
    
    # Try to parse the date
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
        return parsed
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD")


def parse_datetime(datetime_str: str) -> datetime:
    """Parse a datetime string in YYYY-MM-DD HH:MM:SS format.
    
    Args:
        datetime_str: Datetime string to parse
        
    Returns:
        Parsed datetime object
        
    Raises:
        ValueError: If datetime string is invalid
    """
    # Validate input
    if datetime_str is None:
        raise ValueError("Datetime string cannot be None")
    
    # Strip whitespace
    datetime_str = datetime_str.strip()
    
    # Check for empty string
    if not datetime_str:
        raise ValueError("Datetime string cannot be empty")
    
    # Try to parse the datetime
    try:
        parsed = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
        return parsed
    except ValueError:
        raise ValueError(f"Invalid datetime format: {datetime_str}. Expected YYYY-MM-DD HH:MM:SS")


def format_date(dt: datetime) -> str:
    """Format a datetime as a date string.
    
    Args:
        dt: Datetime to format
        
    Returns:
        Formatted date string in YYYY-MM-DD format
    """
    # Validate input
    if dt is None:
        raise ValueError("Datetime cannot be None")
    
    # Format the date
    return dt.strftime("%Y-%m-%d")


def format_datetime(dt: datetime) -> str:
    """Format a datetime as a full datetime string.
    
    Args:
        dt: Datetime to format
        
    Returns:
        Formatted datetime string in YYYY-MM-DD HH:MM:SS format
    """
    # Validate input
    if dt is None:
        raise ValueError("Datetime cannot be None")
    
    # Format the datetime
    return dt.strftime("%Y-%m-%d %H:%M:%S")

