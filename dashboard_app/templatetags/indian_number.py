"""
Custom template filters for Indian numbering system (lakhs/crores)
"""
from django import template

register = template.Library()


@register.filter
def indian_number(value):
    """
    Format number using Indian numbering system (lakhs/crores).
    Example: 13762563 -> "1,37,62,563"
    Example: 1650 -> "1,650"
    Example: 527 -> "527"
    """
    if value is None:
        return '0'
    
    try:
        # Convert to float first
        num = float(value)
        
        # Handle negative numbers
        is_negative = num < 0
        num = abs(num)
        
        # Split into integer and decimal parts
        if num == int(num):
            # Whole number
            num_str = str(int(num))
            integer_part = num_str
            decimal_part = ''
        else:
            # Decimal number - format with 2 decimal places
            num_str = f"{num:.2f}"
            if '.' in num_str:
                integer_part, decimal_part = num_str.split('.')
            else:
                integer_part = num_str
                decimal_part = ''
        
        # Format integer part with Indian numbering
        if len(integer_part) <= 3:
            formatted_int = integer_part
        else:
            # Reverse for easier processing
            reversed_int = integer_part[::-1]
            parts = []
            
            # First 3 digits
            parts.append(reversed_int[:3])
            remaining = reversed_int[3:]
            
            # Then every 2 digits
            for i in range(0, len(remaining), 2):
                parts.append(remaining[i:i+2])
            
            # Join and reverse back
            formatted_int = ','.join(parts)[::-1]
        
        # Combine with decimal part
        if decimal_part:
            result = f"{formatted_int}.{decimal_part}"
        else:
            result = formatted_int
        
        return f"-{result}" if is_negative else result
    except (ValueError, TypeError):
        return str(value)


@register.filter
def indian_int(value):
    """
    Format integer using Indian numbering system (lakhs/crores).
    Example: 13762563 -> "1,37,62,563"
    Example: 1650 -> "1,650"
    Example: 527 -> "527"
    """
    if value is None:
        return '0'
    
    try:
        num = int(float(value))
        
        # Handle negative numbers
        is_negative = num < 0
        num = abs(num)
        
        # Convert to string
        num_str = str(num)
        
        if len(num_str) <= 3:
            result = num_str
        else:
            # Reverse the string for easier processing
            reversed_str = num_str[::-1]
            
            # First 3 digits, then every 2 digits
            parts = []
            parts.append(reversed_str[:3])  # First 3 digits
            remaining = reversed_str[3:]
            
            # Add commas every 2 digits
            for i in range(0, len(remaining), 2):
                parts.append(remaining[i:i+2])
            
            # Join with commas and reverse back
            result = ','.join(parts)[::-1]
        
        return f"-{result}" if is_negative else result
    except (ValueError, TypeError):
        return str(value)
