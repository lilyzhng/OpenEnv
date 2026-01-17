"""String formatting utilities with obvious duplication."""


def format_name(first_name: str, last_name: str) -> str:
    """Format a person's full name.
    
    Args:
        first_name: The person's first name
        last_name: The person's last name
        
    Returns:
        Formatted full name with proper capitalization
    """
    # Validate inputs
    if first_name is None:
        first_name = ""
    if last_name is None:
        last_name = ""
    
    # Strip whitespace
    first_name = first_name.strip()
    last_name = last_name.strip()
    
    # Check for empty strings
    if not first_name and not last_name:
        return ""
    
    # Capitalize each word
    first_formatted = first_name.title()
    last_formatted = last_name.title()
    
    # Combine with space
    if first_formatted and last_formatted:
        return f"{first_formatted} {last_formatted}"
    elif first_formatted:
        return first_formatted
    else:
        return last_formatted


def format_title(title: str, subtitle: str) -> str:
    """Format a title with optional subtitle.
    
    Args:
        title: The main title
        subtitle: The subtitle
        
    Returns:
        Formatted title string with proper capitalization
    """
    # Validate inputs
    if title is None:
        title = ""
    if subtitle is None:
        subtitle = ""
    
    # Strip whitespace
    title = title.strip()
    subtitle = subtitle.strip()
    
    # Check for empty strings
    if not title and not subtitle:
        return ""
    
    # Capitalize each word
    title_formatted = title.title()
    subtitle_formatted = subtitle.title()
    
    # Combine with separator
    if title_formatted and subtitle_formatted:
        return f"{title_formatted}: {subtitle_formatted}"
    elif title_formatted:
        return title_formatted
    else:
        return subtitle_formatted


def format_email(username: str, domain: str) -> str:
    """Format an email address.
    
    Args:
        username: The username part
        domain: The domain part
        
    Returns:
        Formatted email address in lowercase
    """
    # Validate inputs
    if username is None:
        username = ""
    if domain is None:
        domain = ""
    
    # Strip whitespace
    username = username.strip()
    domain = domain.strip()
    
    # Check for empty strings
    if not username or not domain:
        return ""
    
    # Lowercase both parts
    username_formatted = username.lower()
    domain_formatted = domain.lower()
    
    # Combine with @
    return f"{username_formatted}@{domain_formatted}"

