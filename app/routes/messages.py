from flask import Blueprint, request, jsonify
from sqlalchemy import or_
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.services.messaging_service import MessagingService
from app.utils.base_controller import BaseController
from app.models import User, UserRole, Course, Enrollment

bp = Blueprint('messages', __name__, url_prefix='/api/messages')

@bp.route('/send', methods=['POST'])
@jwt_required()
def send_message():
    """Send a message"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    return BaseController.handle_request(
        MessagingService.send_message,
        user_id,
        data,
        success_message="Message sent successfully",
        success_code=201
    )

@bp.route('/', methods=['GET'])
@jwt_required()
def get_messages():
    """Get messages for current user"""
    user_id = int(get_jwt_identity())
    message_type = request.args.get('type', 'received')  
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    return BaseController.handle_list_request(
        MessagingService.get_messages,
        user_id,
        message_type=message_type,
        page=page,
        per_page=per_page
    )

@bp.route('/<int:message_id>', methods=['GET'])
@jwt_required()
def get_message(message_id):
    """Get a specific message"""
    user_id = int(get_jwt_identity())
    
    return BaseController.handle_request(
        MessagingService.get_message,
        user_id,
        message_id
    )

@bp.route('/<int:message_id>/read', methods=['POST'])
@jwt_required()
def mark_as_read(message_id):
    """Mark a message as read"""
    user_id = int(get_jwt_identity())
    
    return BaseController.handle_request(
        MessagingService.mark_as_read,
        user_id,
        message_id,
        success_message="Message marked as read"
    )

@bp.route('/conversations', methods=['GET'])
@jwt_required()
def get_conversations():
    """Get conversations for current user"""
    user_id = int(get_jwt_identity())
    
    return BaseController.handle_request(
        MessagingService.get_conversations,
        user_id
    )

@bp.route('/conversations/<int:partner_id>', methods=['GET'])
@jwt_required()
def get_conversation_messages(partner_id):
    """Get messages in a conversation with a specific user"""
    user_id = int(get_jwt_identity())
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    return BaseController.handle_list_request(
        MessagingService.get_conversation_messages,
        user_id,
        partner_id,
        page=page,
        per_page=per_page
    )

@bp.route('/search-users', methods=['GET'])
@jwt_required()
def search_users():
    """Search for users that the current user can message"""
    current_user_id = int(get_jwt_identity())
    current_user = User.query.get(current_user_id)
    
    if not current_user:
        return jsonify({'error': 'User not found'}), 404
    
    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', 10, type=int)
    
    if len(query) < 2:
        return jsonify({'users': []})
    
    if current_user.is_admin():
        users_query = User.query.filter(
            User.id != current_user_id,
            User.is_active == True,
            or_(
                User.full_name.ilike(f'%{query}%'),
                User.email.ilike(f'%{query}%'),
                User.username.ilike(f'%{query}%')
            )
        ).limit(limit)
    
    elif current_user.is_teacher():
        # Teachers can message:
        # 1. Students enrolled in their courses
        # 2. Other teachers
        # 3. Admins
        enrolled_student_ids = db.session.query(Enrollment.student_id).filter(
            Enrollment.course_id.in_(
                db.session.query(Course.id).filter_by(teacher_id=current_user_id)
            )
        ).subquery()
        
        users_query = User.query.filter(
            User.id != current_user_id,
            User.is_active == True,
            or_(
                User.full_name.ilike(f'%{query}%'),
                User.email.ilike(f'%{query}%'),
                User.username.ilike(f'%{query}%')
            ),
            or_(
                User.id.in_(enrolled_student_ids), 
                User.role == UserRole.TEACHER,     
                User.role == UserRole.ADMIN      
            )
        ).limit(limit)
    
    elif current_user.is_student():
        # Students can message:
        # 1. Teachers of courses they're enrolled in
        # 2. Admins
        teacher_ids = db.session.query(Course.teacher_id).filter(
            Course.id.in_(
                db.session.query(Enrollment.course_id).filter_by(
                    student_id=current_user_id,
                    status='active'
                )
            )
        ).subquery()
        
        users_query = User.query.filter(
            User.id != current_user_id,
            User.is_active == True,
            or_(
                User.full_name.ilike(f'%{query}%'),
                User.email.ilike(f'%{query}%'),
                User.username.ilike(f'%{query}%')
            ),
            or_(
                User.id.in_(teacher_ids),           
                User.role == UserRole.ADMIN       
            )
        ).limit(limit)
    
    else:
        return jsonify({'users': []})
    
    users = users_query.all()
    
    users_data = []
    for user in users:
        user_dict = user.to_dict()
        if current_user.is_teacher() and user.is_student():
            shared_courses = db.session.query(Course.title).filter(
                Course.teacher_id == current_user_id,
                Course.id.in_(
                    db.session.query(Enrollment.course_id).filter_by(student_id=user.id)
                )
            ).all()
            if shared_courses:
                user_dict['context'] = f"Student in: {', '.join([c.title for c in shared_courses[:2]])}"
                if len(shared_courses) > 2:
                    user_dict['context'] += f" (+{len(shared_courses) - 2} more)"
        
        elif current_user.is_student() and user.is_teacher():
            shared_courses = db.session.query(Course.title).filter(
                Course.teacher_id == user.id,
                Course.id.in_(
                    db.session.query(Enrollment.course_id).filter_by(
                        student_id=current_user_id,
                        status='active'
                    )
                )
            ).all()
            if shared_courses:
                user_dict['context'] = f"Teacher of: {', '.join([c.title for c in shared_courses[:2]])}"
                if len(shared_courses) > 2:
                    user_dict['context'] += f" (+{len(shared_courses) - 2} more)"
        
        users_data.append(user_dict)
    
    return jsonify({'users': users_data})