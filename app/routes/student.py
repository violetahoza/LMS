# app/routes/student.py 
from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.student_service import StudentService
from app.utils.base_controller import BaseController
from app.utils.decorators import student_required

bp = Blueprint('student', __name__, url_prefix='/api/student')

@bp.route('/dashboard', methods=['GET'])
@student_required()
def get_dashboard():
    """Get student dashboard data"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        StudentService.get_dashboard,
        user_id
    )

@bp.route('/progress', methods=['GET'])
@student_required()
def get_progress():
    """Get detailed student progress"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        StudentService.get_progress,
        user_id
    )

@bp.route('/achievements', methods=['GET'])
@student_required()
def get_achievements():
    """Get student achievements"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        StudentService.get_achievements,
        user_id
    )

@bp.route('/certificates', methods=['GET'])
@student_required()
def get_certificates():
    """Get student certificates"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        StudentService.get_certificates,
        user_id
    )

@bp.route('/certificates/request/<int:course_id>', methods=['POST'])
@student_required()
def request_certificate(course_id):
    """Request certificate for completed course"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        StudentService.request_certificate,
        user_id,
        course_id,
        success_message="Certificate requested successfully",
        success_code=201
    )

@bp.route('/study-streak', methods=['GET'])
@student_required()
def get_study_streak():
    """Get student study streak information"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        StudentService.get_study_streak,
        user_id
    )

@bp.route('/recommendations', methods=['GET'])
@student_required()
def get_course_recommendations():
    """Get course recommendations for student"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        StudentService.get_course_recommendations,
        user_id
    )