# app/routes/quizzes.py
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.quiz_service import QuizService
from app.services.achievement_service import AchievementService
from app.utils.base_controller import BaseController
from app.utils.decorators import teacher_required, student_required
from app.utils.validators import validate_quiz_answers

bp = Blueprint('quizzes', __name__, url_prefix='/api/quizzes')

@bp.route('/course/<int:course_id>', methods=['GET'])
@jwt_required()
def get_course_quizzes(course_id):
    """Get all quizzes for a course"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        QuizService.get_course_quizzes,
        user_id,
        course_id
    )

@bp.route('/<int:quiz_id>', methods=['GET'])
@jwt_required()
def get_quiz(quiz_id):
    """Get a specific quiz"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        QuizService.get_quiz,
        user_id,
        quiz_id
    )

@bp.route('/', methods=['POST'])
@teacher_required()
def create_quiz():
    """Create a new quiz"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        QuizService.create_quiz,
        user_id,
        request.get_json(),
        success_message="Quiz created successfully",
        success_code=201
    )

@bp.route('/<int:quiz_id>/questions', methods=['POST'])
@teacher_required()
def add_question(quiz_id):
    """Add a question to a quiz"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        QuizService.add_question,
        user_id,
        quiz_id,
        request.get_json(),
        success_message="Question added successfully",
        success_code=201
    )

@bp.route('/<int:quiz_id>/start', methods=['POST'])
@student_required()
def start_quiz(quiz_id):
    """Start a quiz attempt"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        QuizService.start_quiz,
        user_id,
        quiz_id,
        success_message="Quiz started successfully"
    )

@bp.route('/attempt/<int:attempt_id>/submit', methods=['POST'])
@student_required()
def submit_quiz(attempt_id):
    """Submit quiz answers"""
    user_id = get_jwt_identity()
    data = request.get_json()
    answers = data.get('answers', {})
    
    # Handle the submission and achievement checking in the service
    return BaseController.handle_request(
        QuizService.submit_quiz_with_achievements,
        user_id,
        attempt_id,
        answers,
        success_message="Quiz submitted successfully"
    )

@bp.route('/attempt/<int:attempt_id>/results', methods=['GET'])
@jwt_required()
def get_quiz_results(attempt_id):
    """Get quiz results"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        QuizService.get_quiz_results,
        user_id,
        attempt_id
    )

@bp.route('/<int:quiz_id>/statistics', methods=['GET'])
@teacher_required()
def get_quiz_statistics(quiz_id):
    """Get quiz statistics (teacher only)"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        QuizService.get_quiz_statistics,
        user_id,
        quiz_id
    )