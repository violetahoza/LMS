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
        int(user_id),
        course_id
    )

@bp.route('/<int:quiz_id>', methods=['GET'])
@jwt_required()
def get_quiz(quiz_id):
    """Get a specific quiz"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        QuizService.get_quiz,
        int(user_id),
        quiz_id
    )

@bp.route('/', methods=['POST'])
@teacher_required()
def create_quiz():
    """Create a new quiz"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        QuizService.create_quiz,
        int(user_id),
        request.get_json(),
        success_message="Quiz created successfully",
        success_code=201
    )

@bp.route('/<int:quiz_id>', methods=['PUT'])
@teacher_required()
def update_quiz(quiz_id):
    """Update a quiz"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        QuizService.update_quiz,
        int(user_id),
        quiz_id,
        request.get_json(),
        success_message="Quiz updated successfully"
    )

@bp.route('/<int:quiz_id>', methods=['DELETE'])
@teacher_required()
def delete_quiz(quiz_id):
    """Delete a quiz"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        QuizService.delete_quiz,
        int(user_id),
        quiz_id,
        success_message="Quiz deleted successfully"
    )

@bp.route('/<int:quiz_id>/questions', methods=['POST'])
@teacher_required()
def add_question(quiz_id):
    """Add a question to a quiz"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        QuizService.add_question,
        int(user_id),
        quiz_id,
        request.get_json(),
        success_message="Question added successfully",
        success_code=201
    )

@bp.route('/<int:quiz_id>/questions/<int:question_id>', methods=['PUT'])
@teacher_required()
def update_question(quiz_id, question_id):
    """Update a question"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        QuizService.update_question,
        int(user_id),
        quiz_id,
        question_id,
        request.get_json(),
        success_message="Question updated successfully"
    )

@bp.route('/<int:quiz_id>/questions/<int:question_id>', methods=['DELETE'])
@teacher_required()
def delete_question(quiz_id, question_id):
    """Delete a question"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        QuizService.delete_question,
        int(user_id),
        quiz_id,
        question_id,
        success_message="Question deleted successfully"
    )

@bp.route('/<int:quiz_id>/start', methods=['POST'])
@student_required()
def start_quiz(quiz_id):
    """Start a quiz attempt"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        QuizService.start_quiz,
        int(user_id),
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
    
    return BaseController.handle_request(
        QuizService.submit_quiz_with_achievements,
        int(user_id),
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
        int(user_id),
        attempt_id
    )

@bp.route('/<int:quiz_id>/statistics', methods=['GET'])
@teacher_required()
def get_quiz_statistics(quiz_id):
    """Get quiz statistics (teacher only)"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        QuizService.get_quiz_statistics,
        int(user_id),
        quiz_id
    )