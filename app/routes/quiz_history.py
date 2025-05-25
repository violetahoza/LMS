from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.quiz_history_service import QuizHistoryService
from app.utils.base_controller import BaseController
from app.utils.decorators import student_required

bp = Blueprint('quiz_history', __name__, url_prefix='/api/quiz-history')

@bp.route('/', methods=['GET'])
@student_required()
def get_quiz_history():
    """Get comprehensive quiz history for student"""
    student_id = int(get_jwt_identity())
    course_id = request.args.get('course_id', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    return BaseController.handle_list_request(
        QuizHistoryService.get_student_quiz_history,
        student_id,
        course_id=course_id,
        page=page,
        per_page=per_page
    )

@bp.route('/attempt/<int:attempt_id>', methods=['GET'])
@student_required()
def get_attempt_details(attempt_id):
    """Get detailed information about a specific quiz attempt"""
    student_id = int(get_jwt_identity())
    
    return BaseController.handle_request(
        QuizHistoryService.get_quiz_attempt_details,
        student_id,
        attempt_id
    )

@bp.route('/quiz/<int:quiz_id>/analytics', methods=['GET'])
@student_required()
def get_quiz_analytics(quiz_id):
    """Get performance analytics for a specific quiz"""
    student_id = int(get_jwt_identity())
    
    return BaseController.handle_request(
        QuizHistoryService.get_quiz_performance_analytics,
        student_id,
        quiz_id
    )

@bp.route('/course/<int:course_id>/summary', methods=['GET'])
@student_required()
def get_course_quiz_summary(course_id):
    """Get summary of all quizzes in a course"""
    student_id = int(get_jwt_identity())
    
    return BaseController.handle_request(
        QuizHistoryService.get_course_quiz_summary,
        student_id,
        course_id
    )