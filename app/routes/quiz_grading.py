from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.quiz_grading_service import QuizGradingService
from app.utils.base_controller import BaseController
from app.utils.decorators import teacher_required

bp = Blueprint('quiz_grading', __name__, url_prefix='/api/quiz-grading')

@bp.route('/pending', methods=['GET'])
@teacher_required()
def get_pending_grading():
    """Get quiz attempts that need manual grading"""
    teacher_id = int(get_jwt_identity())
    
    return BaseController.handle_request(
        QuizGradingService.get_pending_quiz_grading,
        teacher_id
    )

@bp.route('/attempt/<int:attempt_id>', methods=['GET'])
@teacher_required()
def get_attempt_for_grading(attempt_id):
    """Get detailed quiz attempt for grading"""
    teacher_id = int(get_jwt_identity())
    
    return BaseController.handle_request(
        QuizGradingService.get_attempt_for_grading,
        teacher_id,
        attempt_id
    )

@bp.route('/grade-answer', methods=['POST'])
@teacher_required()
def grade_short_answer():
    """Grade a specific short answer question"""
    teacher_id = int(get_jwt_identity())
    data = request.get_json()
    
    return BaseController.handle_request(
        QuizGradingService.grade_short_answer,
        teacher_id,
        data['answer_id'],
        data['is_correct'],
        data.get('points_awarded'),
        success_message="Answer graded successfully"
    )

@bp.route('/bulk-grade', methods=['POST'])
@teacher_required()
def bulk_grade_answers():
    """Grade multiple short answer questions at once"""
    teacher_id = int(get_jwt_identity())
    data = request.get_json()
    
    return BaseController.handle_request(
        QuizGradingService.bulk_grade_answers,
        teacher_id,
        data['grading_data'],
        success_message="Answers graded successfully"
    )

@bp.route('/quiz/<int:quiz_id>/history', methods=['GET'])
@teacher_required()
def get_quiz_grading_history(quiz_id):
    """Get grading history for a specific quiz"""
    teacher_id = int(get_jwt_identity())
    
    return BaseController.handle_request(
        QuizGradingService.get_quiz_grading_history,
        teacher_id,
        quiz_id
    )