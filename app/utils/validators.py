import re
from datetime import datetime
import os
from werkzeug.utils import secure_filename

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one digit"
    return True, "Password is valid"

def validate_phone(phone):
    """Validate phone number format"""
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    pattern = r'^\+?\d{10,15}$'
    return re.match(pattern, cleaned) is not None

def validate_username(username):
    """Validate username format"""
    if len(username) < 3:
        return False, "Username must be at least 3 characters long"
    if len(username) > 30:
        return False, "Username must be less than 30 characters"
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "Username can only contain letters, numbers, and underscores"
    return True, "Username is valid"

def validate_date_range(start_date, end_date):
    """Validate that end date is after start date"""
    if isinstance(start_date, str):
        start_date = datetime.fromisoformat(start_date)
    if isinstance(end_date, str):
        end_date = datetime.fromisoformat(end_date)
    
    if end_date <= start_date:
        return False, "End date must be after start date"
    return True, "Date range is valid"

def allowed_file(filename, allowed_extensions):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def validate_file_size(file_size, max_size):
    """Validate file size"""
    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        return False, f"File size exceeds maximum allowed size of {max_mb}MB"
    return True, "File size is valid"

def sanitize_filename(filename):
    """Sanitize filename for safe storage"""
    name, ext = os.path.splitext(filename)
    name = secure_filename(name)
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    return f"{name}_{timestamp}{ext}"

def validate_quiz_answers(questions, answers):
    """Validate quiz answer format"""
    errors = []
    
    if not isinstance(answers, dict):
        return False, ["Answers must be provided as a dictionary"]
    
    for question in questions:
        question_id = str(question.id)
        if question_id not in answers:
            errors.append(f"Answer missing for question {question_id}")
            continue
        
        answer = answers[question_id]
        
        if question.question_type == 'multiple_choice':
            if not isinstance(answer, int):
                errors.append(f"Answer for question {question_id} must be an option ID")
        elif question.question_type == 'true_false':
            if not isinstance(answer, int):
                errors.append(f"Answer for question {question_id} must be an option ID")
        elif question.question_type == 'short_answer':
            if not isinstance(answer, str) or len(answer.strip()) == 0:
                errors.append(f"Answer for question {question_id} must be a non-empty string")
    
    if errors:
        return False, errors
    return True, "All answers are valid"

def validate_grade(grade, max_grade):
    """Validate grade value"""
    try:
        grade = float(grade)
        if grade < 0:
            return False, "Grade cannot be negative"
        if grade > max_grade:
            return False, f"Grade cannot exceed maximum of {max_grade}"
        return True, "Grade is valid"
    except (TypeError, ValueError):
        return False, "Grade must be a number"