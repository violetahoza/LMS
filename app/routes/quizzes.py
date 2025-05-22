from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from app.models import db, User, Course, Quiz, Question, AnswerOption, QuizAttempt, Enrollment
from app.services.quiz_service import QuizService
from app.services.achievement_service import AchievementService
from app.utils.decorators import teacher_required, student_required
from app.utils.validators import validate_quiz_answers

bp = Blueprint('quizzes', __name__, url_prefix='/api/quizzes')

@bp.route('/course/<int:course_id>', methods=['GET'])
@jwt_required()
def get_course_quizzes(course_id):
    """Get all quizzes for a course"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        course = Course.query.get(course_id)
        
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        # Check access permissions
        if not user.can_access_course(course):
            return jsonify({'error': 'Access denied'}), 403
        
        quizzes = course.quizzes.all()
        quizzes_data = []
        
        for quiz in quizzes:
            quiz_dict = quiz.to_dict()
            
            # Add attempt info for students
            if user.is_student():
                attempts = QuizAttempt.query.filter_by(
                    student_id=user_id,
                    quiz_id=quiz.id
                ).all()
                
                quiz_dict['attempts'] = {
                    'count': len(attempts),
                    'remaining': quiz.max_attempts - len(attempts),
                    'best_score': max([a.score for a in attempts if a.score is not None], default=0) if attempts else 0,
                    'has_passed': any(a.score >= quiz.passing_score for a in attempts if a.score is not None)
                }
            
            quizzes_data.append(quiz_dict)
        
        return jsonify({
            'quizzes': quizzes_data,
            'total': len(quizzes_data)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:quiz_id>', methods=['GET'])
@jwt_required()
def get_quiz(quiz_id):
    """Get a specific quiz"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        quiz = Quiz.query.get(quiz_id)
        
        if not quiz:
            return jsonify({'error': 'Quiz not found'}), 404
        
        # Check access permissions
        if not user.can_access_course(quiz.course):
            return jsonify({'error': 'Access denied'}), 403
        
        quiz_data = quiz.to_dict()
        
        # Add questions for teachers or during quiz attempt
        if user.is_teacher() and quiz.course.teacher_id == user_id:
            quiz_data['questions'] = QuizService.get_quiz_questions(quiz_id, include_answers=True)
        
        # Add attempt info for students
        if user.is_student():
            can_retake, message = QuizService.can_retake_quiz(user_id, quiz_id)
            quiz_data['can_take'] = can_retake
            quiz_data['message'] = message
            quiz_data['attempts'] = QuizService.get_student_quiz_attempts(user_id, quiz_id)
        
        return jsonify(quiz_data), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/', methods=['POST'])
@teacher_required()
def create_quiz():
    """Create a new quiz"""
    try:
        data = request.get_json()
        user_id = get_jwt_identity()
        
        # Validate required fields
        required_fields = ['course_id', 'title']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check course ownership
        course = Course.query.get(data['course_id'])
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        if course.teacher_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Create quiz
        quiz = Quiz(
            course_id=data['course_id'],
            lesson_id=data.get('lesson_id'),
            title=data['title'],
            description=data.get('description'),
            total_points=data.get('total_points', 100),
            passing_score=data.get('passing_score', 60),
            time_limit_minutes=data.get('time_limit_minutes'),
            max_attempts=data.get('max_attempts', 3)
        )
        
        db.session.add(quiz)
        db.session.commit()
        
        return jsonify({
            'message': 'Quiz created successfully',
            'quiz': quiz.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:quiz_id>/questions', methods=['POST'])
@teacher_required()
def add_question(quiz_id):
    """Add a question to a quiz"""
    try:
        data = request.get_json()
        user_id = get_jwt_identity()
        quiz = Quiz.query.get(quiz_id)
        
        if not quiz:
            return jsonify({'error': 'Quiz not found'}), 404
        
        # Check ownership
        if quiz.course.teacher_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Validate required fields
        required_fields = ['question_text', 'question_type', 'order_number']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Create question
        question = Question(
            quiz_id=quiz_id,
            question_text=data['question_text'],
            question_type=data['question_type'],
            points=data.get('points', 10),
            order_number=data['order_number']
        )
        
        db.session.add(question)
        db.session.flush()  # Get question ID
        
        # Add answer options for multiple choice and true/false
        if data['question_type'] in ['multiple_choice', 'true_false']:
            options = data.get('options', [])
            if not options:
                return jsonify({'error': 'Options are required for this question type'}), 400
            
            for option in options:
                answer_option = AnswerOption(
                    question_id=question.id,
                    option_text=option['text'],
                    is_correct=option.get('is_correct', False)
                )
                db.session.add(answer_option)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Question added successfully',
            'question': question.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:quiz_id>/start', methods=['POST'])
@student_required()
def start_quiz(quiz_id):
    """Start a quiz attempt"""
    try:
        user_id = get_jwt_identity()
        
        # Check enrollment
        quiz = Quiz.query.get(quiz_id)
        if not quiz:
            return jsonify({'error': 'Quiz not found'}), 404
        
        enrollment = Enrollment.query.filter_by(
            student_id=user_id,
            course_id=quiz.course_id,
            status='active'
        ).first()
        
        if not enrollment:
            return jsonify({'error': 'Not enrolled in this course'}), 403
        
        # Check if can take quiz
        can_take, message = QuizService.can_retake_quiz(user_id, quiz_id)
        if not can_take:
            return jsonify({'error': message}), 400
        
        # Create quiz attempt
        attempt = QuizService.create_quiz_attempt(quiz_id, user_id)
        
        # Get questions (without answers)
        questions = QuizService.get_quiz_questions(quiz_id, include_answers=False)
        
        return jsonify({
            'attempt_id': attempt.id,
            'quiz': quiz.to_dict(),
            'questions': questions,
            'started_at': attempt.started_at.isoformat()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/attempt/<int:attempt_id>/submit', methods=['POST'])
@student_required()
def submit_quiz(attempt_id):
    """Submit quiz answers"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validate attempt ownership
        attempt = QuizAttempt.query.get(attempt_id)
        if not attempt:
            return jsonify({'error': 'Quiz attempt not found'}), 404
        
        if attempt.student_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Validate answers
        answers = data.get('answers', {})
        questions = attempt.quiz.questions.all()
        
        valid, errors = validate_quiz_answers(questions, answers)
        if not valid:
            return jsonify({'error': 'Invalid answers', 'details': errors}), 400
        
        # Submit and grade
        result = QuizService.submit_quiz_attempt(attempt_id, answers)
        
        # Check for achievements
        achievements = AchievementService.check_quiz_achievement(user_id, attempt_id)
        
        response = {
            'message': 'Quiz submitted successfully',
            'result': result
        }
        
        if achievements:
            response['achievements_earned'] = [
                {
                    'name': a.name,
                    'description': a.description,
                    'points': a.points_value
                }
                for a in achievements
            ]
        
        return jsonify(response), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/attempt/<int:attempt_id>/results', methods=['GET'])
@jwt_required()
def get_quiz_results(attempt_id):
    """Get quiz results"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        # Get attempt
        attempt = QuizAttempt.query.get(attempt_id)
        if not attempt:
            return jsonify({'error': 'Quiz attempt not found'}), 404
        
        # Check access
        if user.is_student() and attempt.student_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        elif user.is_teacher() and attempt.quiz.course.teacher_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get detailed results
        results = QuizService.get_quiz_results(attempt_id)
        
        return jsonify(results), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:quiz_id>/statistics', methods=['GET'])
@teacher_required()
def get_quiz_statistics(quiz_id):
    """Get quiz statistics (teacher only)"""
    try:
        user_id = get_jwt_identity()
        quiz = Quiz.query.get(quiz_id)
        
        if not quiz:
            return jsonify({'error': 'Quiz not found'}), 404
        
        # Check ownership
        if quiz.course.teacher_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get all completed attempts
        attempts = QuizAttempt.query.filter_by(
            quiz_id=quiz_id,
            status='completed'
        ).all()
        
        from app.utils.helpers import calculate_quiz_statistics
        stats = calculate_quiz_statistics(attempts)
        
        # Get question-level statistics
        question_stats = []
        for question in quiz.questions:
            correct_count = 0
            total_answers = 0
            
            for attempt in attempts:
                answer = next((a for a in attempt.student_answers if a.question_id == question.id), None)
                if answer:
                    total_answers += 1
                    if answer.is_correct:
                        correct_count += 1
            
            question_stats.append({
                'question_id': question.id,
                'question_text': question.question_text,
                'total_answers': total_answers,
                'correct_answers': correct_count,
                'accuracy_rate': (correct_count / total_answers * 100) if total_answers > 0 else 0
            })
        
        return jsonify({
            'quiz': quiz.to_dict(),
            'statistics': stats,
            'question_statistics': question_stats
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500