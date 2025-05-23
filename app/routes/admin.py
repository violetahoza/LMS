# app/routes/admin.py 
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.admin_service import AdminService
from app.utils.base_controller import BaseController
from app.utils.decorators import admin_required

bp = Blueprint('admin', __name__, url_prefix='/api/admin')

@bp.route('/dashboard', methods=['GET'])
@admin_required()
def get_dashboard():
    """Get admin dashboard statistics"""
    return BaseController.handle_request(
        AdminService.get_dashboard
    )

@bp.route('/users', methods=['GET'])
@admin_required()
def get_users():
    """Get all users with filtering and pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    role = request.args.get('role')
    active_only = request.args.get('active_only', 'false').lower() == 'true'
    search = request.args.get('search')
    
    return BaseController.handle_list_request(
        AdminService.get_users,
        page=page,
        per_page=per_page,
        role=role,
        active_only=active_only,
        search=search
    )

@bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required()
def get_user(user_id):
    """Get detailed user information"""
    return BaseController.handle_request(
        AdminService.get_user,
        user_id
    )

@bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@admin_required()
def toggle_user_active(user_id):
    """Toggle user active status"""
    admin_id = get_jwt_identity()
    return BaseController.handle_request(
        AdminService.toggle_user_active,
        admin_id,
        user_id,
        success_message="User status toggled successfully"
    )

@bp.route('/courses', methods=['GET'])
@admin_required()
def get_all_courses():
    """Get all courses with detailed information"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    category = request.args.get('category')
    published_only = request.args.get('published_only', 'false').lower() == 'true'
    
    return BaseController.handle_list_request(
        AdminService.get_all_courses,
        page=page,
        per_page=per_page,
        category=category,
        published_only=published_only
    )

@bp.route('/courses/<int:course_id>/toggle-published', methods=['POST'])
@admin_required()
def toggle_course_published(course_id):
    """Toggle course published status"""
    return BaseController.handle_request(
        AdminService.toggle_course_published,
        course_id,
        success_message="Course status toggled successfully"
    )

@bp.route('/reports/user-activity', methods=['GET'])
@admin_required()
def get_user_activity_report():
    """Get user activity report"""
    days = request.args.get('days', 30, type=int)
    return BaseController.handle_request(
        AdminService.get_user_activity_report,
        days
    )

@bp.route('/reports/course-performance', methods=['GET'])
@admin_required()
def get_course_performance_report():
    """Get course performance report"""
    return BaseController.handle_request(
        AdminService.get_course_performance_report
    )

@bp.route('/achievements', methods=['GET'])
@admin_required()
def get_achievements():
    """Get all achievements"""
    return BaseController.handle_request(
        AdminService.get_achievements
    )

@bp.route('/achievements', methods=['POST'])
@admin_required()
def create_achievement():
    """Create a new achievement"""
    return BaseController.handle_request(
        AdminService.create_achievement,
        request.get_json(),
        success_message="Achievement created successfully",
        success_code=201
    )