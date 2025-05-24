from flask import Blueprint, request, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.teacher_service import TeacherService
from app.utils.base_controller import BaseController
from app.utils.decorators import teacher_required

bp = Blueprint('teacher', __name__, url_prefix='/api/teacher')

@bp.route('/dashboard', methods=['GET'])
@teacher_required()
def get_dashboard():
    """Get teacher dashboard data"""
    teacher_id_str = get_jwt_identity()
    try:
        teacher_id = int(teacher_id_str)
    except (ValueError, TypeError):
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(ValueError("Invalid teacher ID")),
            success_message="Dashboard data retrieved"
        )
    
    return BaseController.handle_request(
        TeacherService.get_dashboard,
        teacher_id
    )

@bp.route('/courses', methods=['GET'])
@teacher_required()
def get_teacher_courses():
    """Get all courses for the teacher"""
    teacher_id_str = get_jwt_identity()
    try:
        teacher_id = int(teacher_id_str)
    except (ValueError, TypeError):
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(ValueError("Invalid teacher ID")),
            success_message="Courses retrieved"
        )
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)
    
    return BaseController.handle_list_request(
        TeacherService.get_teacher_courses,
        teacher_id,
        page=page,
        per_page=per_page
    )

@bp.route('/courses/<int:course_id>', methods=['GET'])
@teacher_required()
def get_course_details(course_id):
    """Get detailed course information"""
    teacher_id_str = get_jwt_identity()
    try:
        teacher_id = int(teacher_id_str)
    except (ValueError, TypeError):
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(ValueError("Invalid teacher ID")),
            success_message="Course details retrieved"
        )
    
    return BaseController.handle_request(
        TeacherService.get_course_details,
        teacher_id,
        course_id
    )

@bp.route('/submissions/pending', methods=['GET'])
@teacher_required()
def get_pending_submissions():
    """Get assignments that need grading"""
    teacher_id_str = get_jwt_identity()
    try:
        teacher_id = int(teacher_id_str)
    except (ValueError, TypeError):
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(ValueError("Invalid teacher ID")),
            success_message="Submissions retrieved"
        )
    
    return BaseController.handle_request(
        TeacherService.get_pending_submissions,
        teacher_id
    )

@bp.route('/quiz/<int:quiz_id>/analytics', methods=['GET'])
@teacher_required()
def get_quiz_analytics(quiz_id):
    """Get detailed quiz analytics"""
    teacher_id_str = get_jwt_identity()
    try:
        teacher_id = int(teacher_id_str)
    except (ValueError, TypeError):
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(ValueError("Invalid teacher ID")),
            success_message="Quiz analytics retrieved"
        )
    
    return BaseController.handle_request(
        TeacherService.get_quiz_analytics,
        teacher_id,
        quiz_id
    )

@bp.route('/course/<int:course_id>/students', methods=['GET'])
@teacher_required()
def get_student_progress_report(course_id):
    """Get student progress report for a course"""
    teacher_id_str = get_jwt_identity()
    try:
        teacher_id = int(teacher_id_str)
    except (ValueError, TypeError):
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(ValueError("Invalid teacher ID")),
            success_message="Student progress retrieved"
        )
    
    return BaseController.handle_request(
        TeacherService.get_student_progress_report,
        teacher_id,
        course_id
    )

@bp.route('/course/<int:course_id>/analytics', methods=['GET'])
@teacher_required()
def get_course_analytics(course_id):
    """Get comprehensive course analytics"""
    teacher_id_str = get_jwt_identity()
    try:
        teacher_id = int(teacher_id_str)
    except (ValueError, TypeError):
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(ValueError("Invalid teacher ID")),
            success_message="Course analytics retrieved"
        )
    
    return BaseController.handle_request(
        TeacherService.get_course_analytics,
        teacher_id,
        course_id
    )

@bp.route('/analytics/overview', methods=['GET'])
@teacher_required()
def get_teacher_analytics_overview():
    """Get aggregate analytics for all teacher's courses"""
    teacher_id_str = get_jwt_identity()
    try:
        teacher_id = int(teacher_id_str)
    except (ValueError, TypeError):
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(ValueError("Invalid teacher ID")),
            success_message="Overview analytics retrieved"
        )

    return BaseController.handle_request(
        TeacherService.get_teacher_analytics_overview,
        teacher_id
    )

@bp.route('/student/<int:student_id>/progress', methods=['GET'])
@teacher_required()
def get_individual_student_progress(student_id):
    """Get detailed progress for a student (by teacher)"""
    teacher_id = int(get_jwt_identity())
    course_id = request.args.get('course_id', type=int)

    if not course_id:
        return {'error': 'Missing course_id parameter'}, 400

    return BaseController.handle_request(
        TeacherService.get_individual_student_progress,
        teacher_id,
        student_id,
        course_id
    )

@bp.route('/course/<int:course_id>/students/export', methods=['GET'])
@teacher_required()
def export_course_students(course_id):
    """Export course students to CSV"""
    teacher_id_str = get_jwt_identity()
    try:
        teacher_id = int(teacher_id_str)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid teacher ID'}), 400
    
    try:
        csv_content = TeacherService.export_course_students(teacher_id, course_id)
        
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=course_{course_id}_students.csv'
        
        return response
    except Exception as e:
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(e),
            success_message="Export completed"
        )