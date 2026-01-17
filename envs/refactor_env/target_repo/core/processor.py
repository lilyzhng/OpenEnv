"""Data processor with duplicated validation logic."""

from datetime import datetime
from typing import Dict, Any


class DataProcessor:
    """Processes user data records with validation."""
    
    def __init__(self):
        self.processed_count = 0
        self.error_count = 0
    
    def process_user(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a user record.
        
        Args:
            data: Raw user data
            
        Returns:
            Processed user data with formatted fields
        """
        result = {}
        
        # Format name - duplicated validation pattern
        first_name = data.get("first_name")
        last_name = data.get("last_name")
        
        if first_name is None:
            first_name = ""
        if last_name is None:
            last_name = ""
        
        first_name = first_name.strip()
        last_name = last_name.strip()
        
        if first_name and last_name:
            result["full_name"] = f"{first_name.title()} {last_name.title()}"
        elif first_name:
            result["full_name"] = first_name.title()
        elif last_name:
            result["full_name"] = last_name.title()
        else:
            result["full_name"] = ""
        
        # Format email - duplicated validation pattern
        username = data.get("email_user")
        domain = data.get("email_domain")
        
        if username is None:
            username = ""
        if domain is None:
            domain = ""
            
        username = username.strip()
        domain = domain.strip()
        
        if username and domain:
            result["email"] = f"{username.lower()}@{domain.lower()}"
        else:
            result["email"] = ""
        
        # Parse and format dates - duplicated validation pattern
        birth_date_str = data.get("birth_date")
        if birth_date_str is not None:
            birth_date_str = birth_date_str.strip()
            if birth_date_str:
                try:
                    parsed = datetime.strptime(birth_date_str, "%Y-%m-%d")
                    result["birth_date"] = parsed.strftime("%Y-%m-%d")
                except ValueError:
                    result["birth_date"] = None
            else:
                result["birth_date"] = None
        else:
            result["birth_date"] = None
        
        self.processed_count += 1
        return result
    
    def process_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process an event record.
        
        Args:
            data: Raw event data
            
        Returns:
            Processed event data with formatted fields
        """
        result = {}
        
        # Format title - duplicated validation pattern
        title = data.get("title")
        subtitle = data.get("subtitle")
        
        if title is None:
            title = ""
        if subtitle is None:
            subtitle = ""
        
        title = title.strip()
        subtitle = subtitle.strip()
        
        if title and subtitle:
            result["display_title"] = f"{title.title()}: {subtitle.title()}"
        elif title:
            result["display_title"] = title.title()
        elif subtitle:
            result["display_title"] = subtitle.title()
        else:
            result["display_title"] = ""
        
        # Parse event datetime - duplicated validation pattern
        event_time_str = data.get("event_time")
        if event_time_str is not None:
            event_time_str = event_time_str.strip()
            if event_time_str:
                try:
                    parsed = datetime.strptime(event_time_str, "%Y-%m-%d %H:%M:%S")
                    result["event_time"] = parsed.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    result["event_time"] = None
            else:
                result["event_time"] = None
        else:
            result["event_time"] = None
        
        self.processed_count += 1
        return result
    
    def validate_required_fields(self, data: Dict[str, Any], required: list) -> bool:
        """Validate that required fields are present and non-empty.
        
        Args:
            data: Data dictionary to validate
            required: List of required field names
            
        Returns:
            True if all required fields are present and non-empty
        """
        for field in required:
            value = data.get(field)
            
            # Validate input - duplicated pattern
            if value is None:
                self.error_count += 1
                return False
            
            # Strip and check - duplicated pattern
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    self.error_count += 1
                    return False
        
        return True
    
    def get_stats(self) -> Dict[str, int]:
        """Get processing statistics."""
        return {
            "processed": self.processed_count,
            "errors": self.error_count,
        }

