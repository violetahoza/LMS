from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.course_service import CourseService
from app.utils.base_controller import BaseController
from app.utils.decorators import teacher_required
from app.models import User

bp = Blueprint('courses', __name__, url_prefix='/api/courses')

@bp.route('/', methods=['GET'])
@jwt_required()
def get_courses():
    """Get all courses (filtered based on user role)"""
    user_id = get_jwt_identity()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    category = request.args.get('category')
    search = request.args.get('search')
    
    return BaseController.handle_list_request(
        CourseService.get_courses,
        user_id,
        page=page,
        per_page=per_page,
        category=category,
        search=search
    )

@bp.route('/<int:course_id>', methods=['GET'])
@jwt_required()
def get_course(course_id):
    """Get a specific course"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        CourseService.get_course,
        user_id,
        course_id
    )

@bp.route('/', methods=['POST'])
@teacher_required()
def create_course():
    """Create a new course (teachers only)"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        CourseService.create_course,
        user_id,
        request.get_json(),
        success_message="Course created successfully",
        success_code=201
    )

@bp.route('/<int:course_id>', methods=['PUT'])
@jwt_required()  
def update_course(course_id):
    """Update a course (teachers and admins)"""
    user_id_str = get_jwt_identity()
    
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(ValueError("Invalid user ID")),
            success_message="Course updated successfully"
        )
    
    # Check if user exists and has permission
    user = User.query.get(user_id)
    if not user:
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(ValueError("User not found")),
            success_message="Course updated successfully"
        )
    
    # Allow teachers and admins to update courses
    if not (user.is_teacher() or user.is_admin()):
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(PermissionError("Access denied. Teacher or admin role required")),
            success_message="Course updated successfully"
        )
    
    return BaseController.handle_request(
        CourseService.update_course,
        user_id,
        course_id,
        request.get_json(),
        success_message="Course updated successfully"
    )

@bp.route('/<int:course_id>', methods=['DELETE'])
@jwt_required()  
def delete_course(course_id):
    """Delete a course (teachers and admins)"""
    user_id_str = get_jwt_identity()
    
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(ValueError("Invalid user ID")),
            success_message="Course deleted successfully"
        )
    
    user = User.query.get(user_id)
    if not user:
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(ValueError("User not found")),
            success_message="Course deleted successfully"
        )
    
    if not (user.is_teacher() or user.is_admin()):
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(PermissionError("Access denied. Teacher or admin role required")),
            success_message="Course deleted successfully"
        )
    
    return BaseController.handle_request(
        CourseService.delete_course,
        user_id,
        course_id,
        success_message="Course deleted successfully"
    )

@bp.route('/<int:course_id>/enroll', methods=['POST'])
@jwt_required()
def enroll_in_course(course_id):
    """Enroll in a course (students only)"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        CourseService.enroll_student,
        user_id,
        course_id,
        success_message="Enrolled in course successfully",
        success_code=201
    )

@bp.route('/<int:course_id>/drop', methods=['POST'])
@jwt_required()
def drop_course(course_id):
    """Drop a course (students only)"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        CourseService.drop_course,
        user_id,
        course_id,
        success_message="Course dropped successfully"
    )

@bp.route('/enrolled', methods=['GET'])
@jwt_required()
def get_enrolled_courses():
    """Get courses the student is enrolled in"""
    user_id = get_jwt_identity()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', 'active')
    
    return BaseController.handle_list_request(
        CourseService.get_enrolled_courses,
        user_id,
        page=page,
        per_page=per_page,
        status=status
    )

@bp.route('/<int:course_id>/students', methods=['GET'])
@jwt_required() 
def get_course_students(course_id):
    """Get students enrolled in a course (teachers and admins)"""
    user_id_str = get_jwt_identity()
    
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(ValueError("Invalid user ID")),
            success_message="Students retrieved successfully"
        )
    
    user = User.query.get(user_id)
    if not user:
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(ValueError("User not found")),
            success_message="Students retrieved successfully"
        )
    
    if not (user.is_teacher() or user.is_admin()):
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(PermissionError("Access denied. Teacher or admin role required")),
            success_message="Students retrieved successfully"
        )
    
    return BaseController.handle_request(
        CourseService.get_course_students,
        user_id,
        course_id
    )