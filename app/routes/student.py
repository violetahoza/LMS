# app/routes/student.py
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.student_service import StudentService, MessageService
from app.utils.base_controller import BaseController
from app.utils.decorators import student_required, teacher_required

bp = Blueprint('student', __name__, url_prefix='/api/student')

@bp.route('/dashboard', methods=['GET'])
@student_required()
def get_dashboard():
    """Get student dashboard data"""
    student_id_str = get_jwt_identity()
    try:
        student_id = int(student_id_str)
    except (ValueError, TypeError):
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(ValueError("Invalid student ID")),
            success_message="Dashboard data retrieved"
        )
    
    return BaseController.handle_request(
        StudentService.get_student_dashboard,
        student_id
    )

@bp.route('/progress', methods=['GET'])
@jwt_required()
def get_student_progress():
    """Get student progress (accessible by teachers and the student themselves)"""
    user_id_str = get_jwt_identity()
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(ValueError("Invalid user ID")),
            success_message="Progress retrieved"
        )
    
    student_id = request.args.get('student_id', type=int)
    course_id = request.args.get('course_id', type=int)
    
    # If no student_id provided, assume current user is the student
    if not student_id:
        student_id = user_id
    
    # Check if current user is a teacher viewing student progress
    from app.models import User
    current_user = User.query.get(user_id)
    
    if current_user.is_teacher() and student_id != user_id:
        # Teacher viewing student progress
        return BaseController.handle_request(
            StudentService.get_student_progress,
            user_id,  # teacher_id
            student_id,
            course_id
        )
    elif student_id == user_id:
        # Student viewing their own progress
        return BaseController.handle_request(
            StudentService.get_student_progress,
            None,  # no teacher_id needed
            student_id,
            course_id
        )
    else:
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(PermissionError("Access denied")),
            success_message="Progress retrieved"
        )

# Message routes
@bp.route('/messages', methods=['GET'])
@jwt_required()
def get_messages():
    """Get user's conversations"""
    user_id_str = get_jwt_identity()
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(ValueError("Invalid user ID")),
            success_message="Messages retrieved"
        )
    
    course_id = request.args.get('course_id', type=int)
    
    return BaseController.handle_request(
        MessageService.get_conversations,
        user_id,
        course_id
    )

@bp.route('/messages/send', methods=['POST'])
@jwt_required()
def send_message():
    """Send a message"""
    user_id_str = get_jwt_identity()
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(ValueError("Invalid user ID")),
            success_message="Message sent"
        )
    
    data = request.get_json()
    
    required_fields = ['recipient_id', 'subject', 'content']
    for field in required_fields:
        if not data.get(field):
            return BaseController.handle_request(
                lambda: (_ for _ in ()).throw(ValueError(f"{field} is required")),
                success_message="Message sent"
            )
    
    return BaseController.handle_request(
        MessageService.send_message,
        user_id,
        data['recipient_id'],
        data['subject'],
        data['content'],
        data.get('course_id'),
        success_message="Message sent successfully"
    )

@bp.route('/announcements', methods=['POST'])
@teacher_required()
def create_announcement():
    """Create a course announcement (teachers only)"""
    user_id_str = get_jwt_identity()
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(ValueError("Invalid user ID")),
            success_message="Announcement created"
        )
    
    data = request.get_json()
    
    required_fields = ['course_id', 'title', 'content']
    for field in required_fields:
        if not data.get(field):
            return BaseController.handle_request(
                lambda: (_ for _ in ()).throw(ValueError(f"{field} is required")),
                success_message="Announcement created"
            )
    
    return BaseController.handle_request(
        MessageService.create_announcement,
        user_id,
        data['course_id'],
        data['title'],
        data['content'],
        success_message="Announcement created successfully"
    )