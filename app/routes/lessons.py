from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.lesson_service import LessonService
from app.utils.base_controller import BaseController
from app.utils.decorators import teacher_required

bp = Blueprint('lessons', __name__, url_prefix='/api/lessons')

@bp.route('/course/<int:course_id>', methods=['GET'])
@jwt_required()
def get_course_lessons(course_id):
    """Get all lessons for a course"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        LessonService.get_course_lessons,
        user_id,
        course_id
    )

@bp.route('/<int:lesson_id>', methods=['GET'])
@jwt_required()
def get_lesson(lesson_id):
    """Get a specific lesson"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        LessonService.get_lesson,
        user_id,
        lesson_id
    )

@bp.route('/', methods=['POST'])
@teacher_required()
def create_lesson():
    """Create a new lesson"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        LessonService.create_lesson,
        int(user_id),
        request.get_json(),
        success_message="Lesson created successfully",
        success_code=201
    )

@bp.route('/<int:lesson_id>', methods=['PUT'])
@teacher_required()
def update_lesson(lesson_id):
    """Update a lesson"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        LessonService.update_lesson,
        int(user_id),
        lesson_id,
        request.get_json(),
        success_message="Lesson updated successfully"
    )

@bp.route('/<int:lesson_id>', methods=['DELETE'])
@teacher_required()
def delete_lesson(lesson_id):
    """Delete a lesson"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        LessonService.delete_lesson,
        int(user_id),
        lesson_id,
        success_message="Lesson deleted successfully"
    )

@bp.route('/<int:lesson_id>/complete', methods=['POST'])
@jwt_required()
def complete_lesson(lesson_id):
    """Mark a lesson as complete"""
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    time_spent = data.get('time_spent_minutes')
    
    return BaseController.handle_request(
        LessonService.complete_lesson,
        int(user_id),
        lesson_id,
        time_spent,
        success_message="Lesson marked as complete"
    )