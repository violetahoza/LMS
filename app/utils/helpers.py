import os
import random
import string
from datetime import datetime, timedelta
import hashlib
from flask import current_app
import logging
from typing import Dict, Any, List
from sqlalchemy import func

logger = logging.getLogger(__name__)

def generate_random_string(length=10):
    """Generate a random string of specified length"""
    letters = string.ascii_letters + string.digits
    return ''.join(random.choice(letters) for _ in range(length))

def generate_certificate_code():
    """Generate a unique certificate code"""
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    random_part = generate_random_string(6)
    return f"CERT-{timestamp}-{random_part}"

def calculate_time_spent(start_time, end_time=None):
    """Calculate time spent in minutes"""
    if end_time is None:
        end_time = datetime.utcnow()
    
    if isinstance(start_time, str):
        start_time = datetime.fromisoformat(start_time)
    if isinstance(end_time, str):
        end_time = datetime.fromisoformat(end_time)
    
    duration = end_time - start_time
    return int(duration.total_seconds() / 60)

def format_duration(minutes):
    """Format duration in minutes to human readable format"""
    if minutes < 60:
        return f"{minutes} minutes"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    if hours == 1:
        if remaining_minutes == 0:
            return "1 hour"
        return f"1 hour {remaining_minutes} minutes"
    else:
        if remaining_minutes == 0:
            return f"{hours} hours"
        return f"{hours} hours {remaining_minutes} minutes"

def get_file_extension(filename):
    """Get file extension from filename"""
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

def create_upload_directory(subfolder=None):
    """Create upload directory if it doesn't exist"""
    upload_path = current_app.config['UPLOAD_FOLDER']
    
    if subfolder:
        upload_path = os.path.join(upload_path, subfolder)
    
    if not os.path.exists(upload_path):
        os.makedirs(upload_path)
    
    return upload_path

def delete_file(filepath):
    """Safely delete a file"""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
    except Exception as e:
        logger.error(f"Error deleting file {filepath}: {str(e)}")
    return False

def calculate_quiz_statistics(quiz_attempts):
    """Calculate statistics for quiz attempts"""
    if not quiz_attempts:
        return {
            'total_attempts': 0,
            'average_score': 0,
            'highest_score': 0,
            'lowest_score': 0,
            'pass_rate': 0
        }
    
    scores = [attempt.score for attempt in quiz_attempts if attempt.score is not None]
    
    if not scores:
        return {
            'total_attempts': len(quiz_attempts),
            'average_score': 0,
            'highest_score': 0,
            'lowest_score': 0,
            'pass_rate': 0
        }
    
    passing_score = quiz_attempts[0].quiz.passing_score
    passing_attempts = sum(1 for score in scores if score >= passing_score)
    
    return {
        'total_attempts': len(quiz_attempts),
        'average_score': sum(scores) / len(scores),
        'highest_score': max(scores),
        'lowest_score': min(scores),
        'pass_rate': (passing_attempts / len(scores)) * 100
    }

def calculate_course_statistics(course):
    """Calculate statistics for a course"""
    active_enrollments = course.enrollments.filter_by(status='active').all()
    completed_enrollments = course.enrollments.filter_by(status='completed').all()
    
    total_lessons = course.lessons.count()
    total_quizzes = course.quizzes.count()
    total_assignments = course.assignments.count()
    
    completion_times = []
    for enrollment in completed_enrollments:
        if enrollment.enrolled_at and enrollment.completed_at:
            days = (enrollment.completed_at - enrollment.enrolled_at).days
            completion_times.append(days)
    
    avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0
    
    return {
        'total_students': len(active_enrollments) + len(completed_enrollments),
        'active_students': len(active_enrollments),
        'completed_students': len(completed_enrollments),
        'completion_rate': (len(completed_enrollments) / (len(active_enrollments) + len(completed_enrollments)) * 100) if (active_enrollments or completed_enrollments) else 0,
        'total_lessons': total_lessons,
        'total_quizzes': total_quizzes,
        'total_assignments': total_assignments,
        'average_completion_days': avg_completion_time
    }

def paginate_query(query, page, per_page):
    """Helper function to paginate SQLAlchemy queries"""
    total = query.count()
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    
    return {
        'items': items,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    }

def check_achievement_criteria(user, achievement):
    """Check if user meets achievement criteria"""
    from app.models import QuizAttempt, Enrollment, LessonProgress
    
    if achievement.criteria_type == 'course_completion':
        completed_courses = Enrollment.query.filter_by(
            student_id=user.id,
            status='completed'
        ).count()
        return completed_courses >= achievement.criteria_value
    
    elif achievement.criteria_type == 'quiz_score':
        high_scores = QuizAttempt.query.filter_by(
            student_id=user.id
        ).filter(
            QuizAttempt.score >= achievement.criteria_value
        ).count()
        return high_scores > 0
    
    elif achievement.criteria_type == 'streak':
        # Check for consecutive days of activity
        return False
    
    elif achievement.criteria_type == 'participation':
        lesson_count = LessonProgress.query.filter_by(
            student_id=user.id
        ).count()
        return lesson_count >= achievement.criteria_value
    
    return False

def format_datetime(dt, format='%Y-%m-%d %H:%M:%S'):
    """Format datetime object to string"""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.strftime(format)

def parse_datetime(date_string):
    """Parse datetime string to datetime object"""
    if date_string is None:
        return None
    if isinstance(date_string, datetime):
        return date_string
    
    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d',
        '%Y-%m-%dT%H:%M:%S.%fZ'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Unable to parse datetime: {date_string}")

def calculate_progress_percentage(completed_items, total_items):
    """Calculate progress percentage"""
    if total_items == 0:
        return 0
    return round((completed_items / total_items) * 100, 2)

def generate_temp_password():
    """Generate a temporary password"""
    return generate_random_string(12)

def hash_file(filepath):
    """Generate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()