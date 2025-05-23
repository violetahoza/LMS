from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from werkzeug.utils import secure_filename
import os

from app.models import db, User, Course, Assignment, AssignmentSubmission, Enrollment
from app.utils.decorators import teacher_required, student_required
from app.utils.validators import allowed_file, validate_file_size, sanitize_filename
from app.utils.helpers import create_upload_directory, delete_file

bp = Blueprint('assignments', __name__, url_prefix='/api/assignments')

@bp.route('/course/<int:course_id>', methods=['GET'])
@jwt_required()
def get_course_assignments(course_id):
    """Get all assignments for a course"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        course = Course.query.get(course_id)
        
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        # Check access permissions
        if not user.can_access_course(course):
            return jsonify({'error': 'Access denied'}), 403
        
        assignments = course.assignments.order_by(Assignment.due_date).all()
        assignments_data = []
        
        for assignment in assignments:
            assignment_dict = assignment.to_dict()
            
            # Add submission info for students
            if user.is_student():
                submission = AssignmentSubmission.query.filter_by(
                    student_id=user_id,
                    assignment_id=assignment.id
                ).first()
                
                assignment_dict['submission'] = submission.to_dict() if submission else None
                assignment_dict['submitted'] = submission is not None
                assignment_dict['overdue'] = (
                    assignment.due_date and 
                    assignment.due_date < datetime.utcnow() and 
                    not submission
                )
            
            # Add submission count for teachers
            elif user.is_teacher() and course.teacher_id == user_id:
                assignment_dict['submission_count'] = assignment.submissions.count()
                assignment_dict['graded_count'] = assignment.submissions.filter_by(status='graded').count()
            
            assignments_data.append(assignment_dict)
        
        return jsonify({
            'assignments': assignments_data,
            'total': len(assignments_data)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:assignment_id>', methods=['GET'])
@jwt_required()
def get_assignment(assignment_id):
    """Get a specific assignment"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        assignment = Assignment.query.get(assignment_id)
        
        if not assignment:
            return jsonify({'error': 'Assignment not found'}), 404
        
        # Check access permissions
        if not user.can_access_course(assignment.course):
            return jsonify({'error': 'Access denied'}), 403
        
        assignment_data = assignment.to_dict()
        
        # Add submission info for students
        if user.is_student():
            submission = AssignmentSubmission.query.filter_by(
                student_id=user_id,
                assignment_id=assignment_id
            ).first()
            
            assignment_data['submission'] = submission.to_dict() if submission else None
            assignment_data['can_submit'] = (
                not submission or 
                submission.status == 'returned'
            ) and (
                not assignment.due_date or 
                assignment.due_date > datetime.utcnow()
            )
        
        return jsonify(assignment_data), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/', methods=['POST'])
@teacher_required()
def create_assignment():
    """Create a new assignment"""
    try:
        data = request.get_json()
        user_id = get_jwt_identity()
        
        # Validate required fields
        required_fields = ['course_id', 'title', 'description']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check course ownership
        course = Course.query.get(data['course_id'])
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        if course.teacher_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Parse due date
        due_date = None
        if data.get('due_date'):
            try:
                due_date = datetime.fromisoformat(data['due_date'])
            except ValueError:
                return jsonify({'error': 'Invalid due date format'}), 400
        
        # Create assignment
        assignment = Assignment(
            course_id=data['course_id'],
            lesson_id=data.get('lesson_id'),
            title=data['title'],
            description=data['description'],
            due_date=due_date,
            total_points=data.get('total_points', 100)
        )
        
        db.session.add(assignment)
        db.session.commit()
        
        return jsonify({
            'message': 'Assignment created successfully',
            'assignment': assignment.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:assignment_id>', methods=['PUT'])
@teacher_required()
def update_assignment(assignment_id):
    """Update an assignment"""
    try:
        data = request.get_json()
        user_id = get_jwt_identity()
        assignment = Assignment.query.get(assignment_id)
        
        if not assignment:
            return jsonify({'error': 'Assignment not found'}), 404
        
        # Check ownership
        if assignment.course.teacher_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Update allowed fields
        allowed_fields = ['title', 'description', 'total_points']
        for field in allowed_fields:
            if field in data:
                setattr(assignment, field, data[field])
        
        # Update due date
        if 'due_date' in data:
            if data['due_date']:
                try:
                    assignment.due_date = datetime.fromisoformat(data['due_date'])
                except ValueError:
                    return jsonify({'error': 'Invalid due date format'}), 400
            else:
                assignment.due_date = None
        
        assignment.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Assignment updated successfully',
            'assignment': assignment.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:assignment_id>', methods=['DELETE'])
@teacher_required()
def delete_assignment(assignment_id):
    """Delete an assignment"""
    try:
        user_id = get_jwt_identity()
        assignment = Assignment.query.get(assignment_id)
        
        if not assignment:
            return jsonify({'error': 'Assignment not found'}), 404
        
        # Check ownership
        if assignment.course.teacher_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Delete associated files
        for submission in assignment.submissions:
            if submission.file_path:
                delete_file(submission.file_path)
        
        db.session.delete(assignment)
        db.session.commit()
        
        return jsonify({'message': 'Assignment deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:assignment_id>/submit', methods=['POST'])
@student_required()
def submit_assignment(assignment_id):
    """Submit an assignment"""
    try:
        user_id = get_jwt_identity()
        assignment = Assignment.query.get(assignment_id)
        
        if not assignment:
            return jsonify({'error': 'Assignment not found'}), 404
        
        # Check enrollment
        enrollment = Enrollment.query.filter_by(
            student_id=user_id,
            course_id=assignment.course_id,
            status='active'
        ).first()
        
        if not enrollment:
            return jsonify({'error': 'Not enrolled in this course'}), 403
        
        # Check if already submitted
        existing_submission = AssignmentSubmission.query.filter_by(
            student_id=user_id,
            assignment_id=assignment_id
        ).first()
        
        # Check if can submit/resubmit
        if existing_submission and existing_submission.status not in ['returned']:
            return jsonify({'error': 'Assignment already submitted'}), 400
        
        # Check due date
        if assignment.due_date and assignment.due_date < datetime.utcnow():
            return jsonify({'error': 'Assignment is past due date'}), 400
        
        # Get submission data
        submission_text = request.form.get('submission_text', '')
        file = request.files.get('file')
        
        if not submission_text and not file:
            return jsonify({'error': 'Either text submission or file is required'}), 400
        
        # Handle file upload
        file_path = None
        if file and file.filename:
            # Validate file
            if not allowed_file(file.filename, current_app.config['ALLOWED_EXTENSIONS']):
                return jsonify({'error': 'File type not allowed'}), 400
            
            # Validate file size
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            
            is_valid, message = validate_file_size(file_size, current_app.config['MAX_CONTENT_LENGTH'])
            if not is_valid:
                return jsonify({'error': message}), 400
            
            # Save file
            upload_dir = create_upload_directory('assignments')
            filename = sanitize_filename(file.filename)
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)
        
        # Create or update submission
        if existing_submission:
            # Update existing submission
            if existing_submission.file_path and file_path:
                delete_file(existing_submission.file_path)
            
            existing_submission.submission_text = submission_text
            existing_submission.file_path = file_path
            existing_submission.submitted_at = datetime.utcnow()
            existing_submission.status = 'submitted'
            existing_submission.grade = None
            existing_submission.feedback = None
            existing_submission.graded_at = None
            existing_submission.graded_by = None
            
            submission = existing_submission
        else:
            # Create new submission
            submission = AssignmentSubmission(
                assignment_id=assignment_id,
                student_id=user_id,
                submission_text=submission_text,
                file_path=file_path,
                status='submitted'
            )
            db.session.add(submission)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Assignment submitted successfully',
            'submission': submission.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        if 'file_path' in locals() and file_path:
            delete_file(file_path)
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:assignment_id>/submissions', methods=['GET'])
@teacher_required()
def get_assignment_submissions(assignment_id):
    """Get all submissions for an assignment (teacher only)"""
    try:
        user_id = get_jwt_identity()
        assignment = Assignment.query.get(assignment_id)
        
        if not assignment:
            return jsonify({'error': 'Assignment not found'}), 404
        
        # Check ownership
        if assignment.course.teacher_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        submissions = assignment.submissions.all()
        submissions_data = []
        
        for submission in submissions:
            submission_data = submission.to_dict()
            submission_data['student'] = submission.student.to_dict()
            submissions_data.append(submission_data)
        
        return jsonify({
            'submissions': submissions_data,
            'total': len(submissions_data),
            'assignment': assignment.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/submissions/<int:submission_id>/grade', methods=['POST'])
@teacher_required()
def grade_submission(submission_id):
    """Grade an assignment submission"""
    try:
        data = request.get_json()
        user_id = get_jwt_identity()
        submission = AssignmentSubmission.query.get(submission_id)
        
        if not submission:
            return jsonify({'error': 'Submission not found'}), 404
        
        # Check ownership
        if submission.assignment.course.teacher_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Validate grade
        if 'grade' not in data:
            return jsonify({'error': 'Grade is required'}), 400
        
        try:
            grade = float(data['grade'])
            if grade < 0 or grade > submission.assignment.total_points:
                return jsonify({
                    'error': f'Grade must be between 0 and {submission.assignment.total_points}'
                }), 400
        except ValueError:
            return jsonify({'error': 'Grade must be a number'}), 400
        
        # Update submission
        submission.grade = grade
        submission.feedback = data.get('feedback', '')
        submission.graded_at = datetime.utcnow()
        submission.graded_by = user_id
        submission.status = 'graded'
        
        db.session.commit()
        
        return jsonify({
            'message': 'Assignment graded successfully',
            'submission': submission.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/submissions/<int:submission_id>/return', methods=['POST'])
@teacher_required()
def return_submission(submission_id):
    """Return submission to student for revision"""
    try:
        data = request.get_json()
        user_id = get_jwt_identity()
        submission = AssignmentSubmission.query.get(submission_id)
        
        if not submission:
            return jsonify({'error': 'Submission not found'}), 404
        
        # Check ownership
        if submission.assignment.course.teacher_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        submission.feedback = data.get('feedback', 'Please revise and resubmit.')
        submission.status = 'returned'
        submission.graded_at = datetime.utcnow()
        submission.graded_by = user_id
        
        db.session.commit()
        
        return jsonify({
            'message': 'Assignment returned to student',
            'submission': submission.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500