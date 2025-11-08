from django.db import models
from django.db.models import Max
from datetime import datetime
from .models import ChangeControlRequest, Department


def generate_temp_cc_number(department_code: str) -> str:
    """
    Generate temporary CC number in format: REQ/CC/YY/DeptCode/00001
    
    Args:
        department_code: Department code (e.g., 'QA', 'PD', 'RA')
    
    Returns:
        Temporary CC number string
    """
    current_year = datetime.now().strftime('%y')
    
    # Find the highest sequence number for this department and year
    prefix = f"REQ/CC/{current_year}/{department_code}/"
    
    # Get all temporary CC numbers that start with this prefix
    existing_numbers = ChangeControlRequest.objects.filter(
        temporary_cc_number__startswith=prefix
    ).values_list('temporary_cc_number', flat=True)
    
    # Extract sequence numbers
    max_sequence = 0
    for number in existing_numbers:
        try:
            # Extract the sequence part (last 5 digits)
            sequence_part = number.split('/')[-1]
            sequence = int(sequence_part)
            if sequence > max_sequence:
                max_sequence = sequence
        except (ValueError, IndexError):
            continue
    
    # Generate next sequence number
    next_sequence = max_sequence + 1
    sequence_str = str(next_sequence).zfill(5)  # Zero-padded to 5 digits
    
    return f"{prefix}{sequence_str}"


def generate_final_cc_number(department_code: str = None) -> str:
    """
    Generate final CC number in format: REQ/CC/YY/DeptCode/00001
    
    If department_code is not provided, uses a generic format.
    
    Args:
        department_code: Optional department code
    
    Returns:
        Final CC number string
    """
    current_year = datetime.now().strftime('%y')
    
    if department_code:
        prefix = f"REQ/CC/{current_year}/{department_code}/"
    else:
        prefix = f"REQ/CC/{current_year}/GEN/"
    
    # Find the highest sequence number for this prefix
    existing_numbers = ChangeControlRequest.objects.filter(
        final_cc_number__startswith=prefix
    ).exclude(final_cc_number__isnull=True).values_list('final_cc_number', flat=True)
    
    # Extract sequence numbers
    max_sequence = 0
    for number in existing_numbers:
        try:
            sequence_part = number.split('/')[-1]
            sequence = int(sequence_part)
            if sequence > max_sequence:
                max_sequence = sequence
        except (ValueError, IndexError):
            continue
    
    # Generate next sequence number
    next_sequence = max_sequence + 1
    sequence_str = str(next_sequence).zfill(5)  # Zero-padded to 5 digits
    
    return f"{prefix}{sequence_str}"


def get_user_department(user):
    """
    Get the department for a user.
    This is a placeholder - you may need to implement based on your user model structure.
    
    Args:
        user: User instance
    
    Returns:
        Department instance or None
    """
    # This is a basic implementation - you may need to adjust based on your user model
    # For example, if users have a profile with department, use that
    # Or if departments are linked via groups, check that
    
    # Try to find department by checking if user is a department head
    try:
        department = Department.objects.get(head=user)
        return department
    except Department.DoesNotExist:
        pass
    
    # Add other logic here based on your user model structure
    # For now, return None and let the calling code handle it
    return None

