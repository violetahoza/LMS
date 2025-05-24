from flask import Blueprint, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.assignment_service import AssignmentService
from app.utils.base_controller import BaseController
from app.utils.decorators import teacher_required, student_required

bp = Blueprint('assignments', __name__, url_prefix='/api/assignments')

@bp.route('/course/<int:course_id>', methods=['GET'])
@jwt_required()
def get_course_assignments(course_id):
    """Get all assignments for a course"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        AssignmentService.get_course_assignments,
        user_id,
        course_id
    )

@bp.route('/<int:assignment_id>', methods=['GET'])
@jwt_required()
def get_assignment(assignment_id):
    """Get a specific assignment"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        AssignmentService.get_assignment,
        user_id,
        assignment_id
    )

@bp.route('/', methods=['POST'])
@teacher_required()
def create_assignment():
    """Create a new assignment"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        AssignmentService.create_assignment,
        user_id,
        request.get_json(),
        success_message="Assignment created successfully",
        success_code=201
    )

@bp.route('/<int:assignment_id>', methods=['PUT'])
@teacher_required()
def update_assignment(assignment_id):
    """Update an assignment"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        AssignmentService.update_assignment,
        int(user_id),
        assignment_id,
        request.get_json(),
        success_message="Assignment updated successfully"
    )

@bp.route('/<int:assignment_id>', methods=['DELETE'])
@teacher_required()
def delete_assignment(assignment_id):
    """Delete an assignment"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        AssignmentService.delete_assignment,
        int(user_id),
        assignment_id,
        success_message="Assignment deleted successfully"
    )

@bp.route('/<int:assignment_id>/submit', methods=['POST'])
@student_required()
def submit_assignment(assignment_id):
    """Submit an assignment"""
    user_id = get_jwt_identity()
    submission_text = request.form.get('submission_text', '')
    file = request.files.get('file')
    max_file_size = current_app.config.get('MAX_CONTENT_LENGTH', 16777216)
    
    return BaseController.handle_request(
        AssignmentService.submit_assignment,
        int(user_id),
        assignment_id,
        submission_text,
        file,
        max_file_size,
        success_message="Assignment submitted successfully",
        success_code=201
    )

@bp.route('/<int:assignment_id>/submissions', methods=['GET'])
@teacher_required()
def get_assignment_submissions(assignment_id):
    """Get all submissions for an assignment (teacher only)"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        AssignmentService.get_assignment_submissions,
        int(user_id),
        assignment_id
    )

@bp.route('/submissions/<int:submission_id>/grade', methods=['POST'])
@teacher_required()
def grade_submission(submission_id):
    """Grade an assignment submission"""
    user_id = get_jwt_identity()
    data = request.get_json()
    
    try:
        grade = float(data.get('grade'))
    except (TypeError, ValueError):
        return BaseController.handle_request(
            lambda: (_ for _ in ()).throw(ValueError("Grade must be a number")),
            success_message="Assignment graded successfully"
        )
    
    feedback = data.get('feedback', '')
    
    return BaseController.handle_request(
        AssignmentService.grade_submission,
        int(user_id),
        submission_id,
        grade,
        feedback,
        success_message="Assignment graded successfully"
    )

@bp.route('/submissions/<int:submission_id>/return', methods=['POST'])
@teacher_required()
def return_submission(submission_id):
    """Return submission to student for revision"""
    user_id = get_jwt_identity()
    data = request.get_json()
    feedback = data.get('feedback', 'Please revise and resubmit.')
    
    return BaseController.handle_request(
        AssignmentService.return_submission,
        int(user_id),
        submission_id,
        feedback,
        success_message="Assignment returned to student"
    )