from datetime import datetime
from typing import Dict, Any, List, Optional
from werkzeug.datastructures import FileStorage
from app.models import db, User, Course, Assignment, AssignmentSubmission, Enrollment
from app.utils.base_controller import ValidationException, PermissionException, NotFoundException
from app.utils.validators import allowed_file, validate_file_size, sanitize_filename
from app.utils.helpers import create_upload_directory, delete_file
import os
from flask import current_app
from app.services.notification_service import NotificationService

class AssignmentService:
    """Service for assignment-related operations"""
    
    @staticmethod
    def get_course_assignments(user_id: int, course_id: int) -> Dict[str, Any]:
        """Get all assignments for a course"""
        user = User.query.get(user_id)
        course = Course.query.get(course_id)
        
        if not course:
            raise NotFoundException("Course not found")
        
        if not user.can_access_course(course):
            raise PermissionException("Access denied")
        
        assignments = course.assignments.order_by(Assignment.due_date).all()
        assignments_data = []
        
        for assignment in assignments:
            assignment_dict = assignment.to_dict()
            
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
            
            elif user.is_teacher() and course.teacher_id == user_id:
                assignment_dict['submission_count'] = assignment.submissions.count()
                assignment_dict['graded_count'] = assignment.submissions.filter_by(status='graded').count()
            
            assignments_data.append(assignment_dict)
        
        return {
            'assignments': assignments_data,
            'total': len(assignments_data)
        }
    
    @staticmethod
    def get_assignment(user_id: int, assignment_id: int) -> Dict[str, Any]:
        """Get a specific assignment"""
        user = User.query.get(user_id)
        assignment = Assignment.query.get(assignment_id)
        
        if not assignment:
            raise NotFoundException("Assignment not found")
        
        if not user.can_access_course(assignment.course):
            raise PermissionException("Access denied")
        
        assignment_data = assignment.to_dict()
        
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
        
        return assignment_data
    
    @staticmethod
    def create_assignment(teacher_id: int, assignment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new assignment"""
        required_fields = ['course_id', 'title', 'description']
        for field in required_fields:
            if field not in assignment_data:
                raise ValidationException(f'{field} is required')
        
        course = Course.query.get(assignment_data['course_id'])
        if not course:
            raise NotFoundException("Course not found")
        
        if course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        due_date = None
        if assignment_data.get('due_date'):
            try:
                due_date = datetime.fromisoformat(assignment_data['due_date'])
            except ValueError:
                raise ValidationException('Invalid due date format')
        
        assignment = Assignment(
            course_id=assignment_data['course_id'],
            lesson_id=assignment_data.get('lesson_id'),
            title=assignment_data['title'],
            description=assignment_data['description'],
            due_date=due_date,
            total_points=assignment_data.get('total_points', 100)
        )
        
        db.session.add(assignment)
        db.session.commit()
        
        return {
            'message': 'Assignment created successfully',
            'assignment': assignment.to_dict()
        }
    
    @staticmethod
    def update_assignment(teacher_id: int, assignment_id: int, assignment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an assignment"""
        assignment = Assignment.query.get(assignment_id)
        if not assignment:
            raise NotFoundException("Assignment not found")
        
        if assignment.course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        allowed_fields = ['title', 'description', 'total_points']
        for field in allowed_fields:
            if field in assignment_data:
                setattr(assignment, field, assignment_data[field])
        
        if 'due_date' in assignment_data:
            if assignment_data['due_date']:
                try:
                    assignment.due_date = datetime.fromisoformat(assignment_data['due_date'])
                except ValueError:
                    raise ValidationException('Invalid due date format')
            else:
                assignment.due_date = None
        
        assignment.updated_at = datetime.utcnow()
        db.session.commit()
        
        return {
            'message': 'Assignment updated successfully',
            'assignment': assignment.to_dict()
        }
    
    @staticmethod
    def delete_assignment(teacher_id: int, assignment_id: int) -> Dict[str, str]:
        """Delete an assignment"""
        assignment = Assignment.query.get(assignment_id)
        if not assignment:
            raise NotFoundException("Assignment not found")
        
        if assignment.course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        # Delete associated files
        for submission in assignment.submissions:
            if submission.file_path:
                delete_file(submission.file_path)
        
        db.session.delete(assignment)
        db.session.commit()
        
        return {'message': 'Assignment deleted successfully'}
    
    @staticmethod
    def submit_assignment(student_id: int, assignment_id: int, submission_text: str, 
                        file: Optional[FileStorage] = None, max_file_size: int = 16777216) -> Dict[str, Any]:
        """Submit an assignment"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise PermissionException("Only students can submit assignments")
        
        assignment = Assignment.query.get(assignment_id)
        if not assignment:
            raise NotFoundException("Assignment not found")
        
        enrollment = Enrollment.query.filter_by(
            student_id=student_id,
            course_id=assignment.course_id
        ).filter(Enrollment.status.in_(['active', 'completed'])).first()
        
        if not enrollment:
            raise PermissionException("Not enrolled in this course")
        
        existing_submission = AssignmentSubmission.query.filter_by(
            student_id=student_id,
            assignment_id=assignment_id
        ).first()
        
        if existing_submission and existing_submission.status not in ['returned']:
            raise ValidationException("Assignment already submitted")
        
        if assignment.due_date and assignment.due_date < datetime.utcnow():
            raise ValidationException("Assignment is past due date")
        
        if not submission_text and not file:
            raise ValidationException("Either text submission or file is required")
        
        file_path = None
        if file and file.filename:
            file_path = AssignmentService._handle_file_upload(file, max_file_size)
        
        try:
            if existing_submission:
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
                submission = AssignmentSubmission(
                    assignment_id=assignment_id,
                    student_id=student_id,
                    submission_text=submission_text,
                    file_path=file_path,
                    status='submitted'
                )
                db.session.add(submission)
            
            enrollment.progress_percentage = enrollment.calculate_progress()
            
            from app.services.lesson_service import LessonService
            course_completed = LessonService._is_course_fully_completed(student_id, assignment.course_id)
            
            if course_completed and enrollment.status == 'active':
                enrollment.status = 'completed'
                enrollment.completed_at = datetime.utcnow()
                NotificationService.notify_course_completion(assignment.course.teacher_id, student_id, assignment.course_id)
            
            db.session.commit()
            
            try:
                NotificationService.notify_assignment_submission(
                    assignment.course.teacher_id, 
                    student_id, 
                    assignment_id
                )
            except Exception as e:
                print(f"Failed to send assignment submission notification: {e}")

            return {
                'message': 'Assignment submitted successfully',
                'submission': submission.to_dict()
            }
        
        except Exception as e:
            if file_path:
                delete_file(file_path)
            raise e

    
    @staticmethod
    def get_assignment_submissions(teacher_id: int, assignment_id: int) -> Dict[str, Any]:
        """Get all submissions for an assignment"""
        assignment = Assignment.query.get(assignment_id)
        if not assignment:
            raise NotFoundException("Assignment not found")
        
        if assignment.course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        submissions = assignment.submissions.all()
        submissions_data = []
        
        for submission in submissions:
            submission_data = submission.to_dict()
            submission_data['student'] = submission.student.to_dict()
            submissions_data.append(submission_data)
        
        return {
            'submissions': submissions_data,
            'total': len(submissions_data),
            'assignment': assignment.to_dict()
        }
    
    @staticmethod
    def grade_submission(teacher_id: int, submission_id: int, grade: float, feedback: str = '') -> Dict[str, Any]:
        """Grade an assignment submission"""
        submission = AssignmentSubmission.query.get(submission_id)
        if not submission:
            raise NotFoundException("Submission not found")
        
        if submission.assignment.course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        if grade < 0 or grade > submission.assignment.total_points:
            raise ValidationException(f'Grade must be between 0 and {submission.assignment.total_points}')
        
        submission.grade = grade
        submission.feedback = feedback
        submission.graded_at = datetime.utcnow()
        submission.graded_by = teacher_id
        submission.status = 'graded'
        
        enrollment = Enrollment.query.filter_by(
            student_id=submission.student_id,
            course_id=submission.assignment.course_id
        ).filter(Enrollment.status.in_(['active', 'completed'])).first()
        
        if enrollment:
            enrollment.progress_percentage = enrollment.calculate_progress()
            
            from app.services.lesson_service import LessonService
            course_completed = LessonService._is_course_fully_completed(submission.student_id, submission.assignment.course_id)
            
            if course_completed and enrollment.status == 'active':
                enrollment.status = 'completed'
                enrollment.completed_at = datetime.utcnow()
                NotificationService.notify_course_completion(teacher_id, submission.student_id, submission.assignment.course_id)
       
        db.session.commit()
        
        try:
            NotificationService.notify_assignment_graded(
                submission.student_id,
                teacher_id,
                submission.assignment_id,
                grade
            )
        except Exception as e:
            print(f"Failed to send grading notification: {e}")

        return {
            'message': 'Assignment graded successfully',
            'submission': submission.to_dict()
        }
    
    @staticmethod
    def return_submission(teacher_id: int, submission_id: int, feedback: str = 'Please revise and resubmit.') -> Dict[str, Any]:
        """Return submission to student for revision"""
        submission = AssignmentSubmission.query.get(submission_id)
        if not submission:
            raise NotFoundException("Submission not found")
        
        if submission.assignment.course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        submission.feedback = feedback
        submission.status = 'returned'
        submission.graded_at = datetime.utcnow()
        submission.graded_by = teacher_id
        
        db.session.commit()
        
        return {
            'message': 'Assignment returned to student',
            'submission': submission.to_dict()
        }
    
    @staticmethod
    def _handle_file_upload(file: FileStorage, max_file_size: int) -> str:
        """Handle file upload for assignment submission"""
        
        allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', {'pdf', 'doc', 'docx', 'txt'})
        if not allowed_file(file.filename, allowed_extensions):
            raise ValidationException('File type not allowed')
        
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        is_valid, message = validate_file_size(file_size, max_file_size)
        if not is_valid:
            raise ValidationException(message)
        
        upload_dir = create_upload_directory('assignments')
        filename = sanitize_filename(file.filename)
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)
        
        return file_path