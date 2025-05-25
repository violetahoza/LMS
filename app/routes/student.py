from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.student_service import StudentService
from app.services.teacher_service import TeacherService
from app.utils.base_controller import BaseController
from app.utils.decorators import student_required
from app.models import User, Course, Enrollment

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
@jwt_required()
def get_student_progress():
    """Get student progress - accessible by teachers and the student themselves"""
    current_user_id = int(get_jwt_identity())
    current_user = User.query.get(current_user_id)
    
    if not current_user:
        return {'error': 'User not found'}, 404
    
    student_id = request.args.get('student_id', type=int)
    course_id = request.args.get('course_id', type=int)
    
    if current_user.is_student():
        if student_id and student_id != current_user_id:
            return {'error': 'Access denied'}, 403
        student_id = current_user_id
        
        if course_id:
            return BaseController.handle_request(
                TeacherService.get_individual_student_progress,
                current_user_id,  #
                student_id,
                course_id
            )
        else:
            return BaseController.handle_request(
                StudentService.get_progress,
                student_id
            )
            
    elif current_user.is_teacher():
        if not student_id:
            return {'error': 'student_id parameter required for teachers'}, 400
        if not course_id:
            return {'error': 'course_id parameter required for teachers'}, 400
            
        course = Course.query.get(course_id)
        if not course or course.teacher_id != current_user_id:
            return {'error': 'Access denied to this course'}, 403
            
        enrollment = Enrollment.query.filter_by(
            student_id=student_id,
            course_id=course_id
        ).first()
        if not enrollment:
            return {'error': 'Student not enrolled in this course'}, 404
            
        return BaseController.handle_request(
            TeacherService.get_individual_student_progress,
            current_user_id,
            student_id,
            course_id
        )
    else:
        return {'error': 'Access denied'}, 403

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

@bp.route('/messages/send', methods=['POST'])
@student_required()
def send_message():
    """Send a message from student"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    from app.services.messaging_service import MessagingService
    return BaseController.handle_request(
        MessagingService.send_message,
        user_id,
        data,
        success_message="Message sent successfully",
        success_code=201
    )

@bp.route('/progress', methods=['GET'])
@jwt_required()
def get_student_progress_by_teacher():
    """Get student progress - accessible by teachers and the student themselves"""
    current_user_id = int(get_jwt_identity())
    current_user = User.query.get(current_user_id)
    
    if not current_user:
        return jsonify({'error': 'User not found'}), 404
    
    student_id = request.args.get('student_id', type=int)
    course_id = request.args.get('course_id', type=int)
    
    if current_user.is_student():
        if student_id and student_id != current_user_id:
            return jsonify({'error': 'Access denied'}), 403
        student_id = current_user_id
    elif current_user.is_teacher():
        if not student_id:
            return jsonify({'error': 'student_id parameter required for teachers'}), 400
        if not course_id:
            return jsonify({'error': 'course_id parameter required for teachers'}), 400
            
        course = Course.query.get(course_id)
        if not course or course.teacher_id != current_user_id:
            return jsonify({'error': 'Access denied to this course'}), 403
            
        enrollment = Enrollment.query.filter_by(
            student_id=student_id,
            course_id=course_id
        ).first()
        if not enrollment:
            return jsonify({'error': 'Student not enrolled in this course'}), 404
    else:
        return jsonify({'error': 'Access denied'}), 403
    
    if course_id:
        return BaseController.handle_request(
            TeacherService.get_individual_student_progress,
            current_user_id if current_user.is_teacher() else student_id,
            student_id,
            course_id
        )
    else:
        return BaseController.handle_request(
            StudentService.get_progress,
            student_id
        )
    

@bp.route('/quiz-attempts', methods=['GET'])
@student_required()
def get_student_quiz_attempts():
    """Get student's quiz attempts"""
    user_id = get_jwt_identity()
    quiz_id = request.args.get('quiz_id', type=int)
    
    from app.services.quiz_service import QuizService
    
    if quiz_id:
        return BaseController.handle_request(
            QuizService.get_student_quiz_attempts,
            int(user_id),
            quiz_id
        )
    else:
        return BaseController.handle_request(
            QuizService.get_student_quiz_attempts,
            int(user_id)
        )

    