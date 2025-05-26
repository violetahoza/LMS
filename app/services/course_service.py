from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import or_
from app.models import db, User, Course, Enrollment, UserRole
from app.utils.base_controller import ValidationException, PermissionException, NotFoundException
from app.services.notification_service import NotificationService

class CourseService:
    """Service for course-related operations"""
    
    @staticmethod
    def get_courses(user_id: int, page: int = 1, per_page: int = 20, 
                   category: Optional[str] = None, search: Optional[str] = None) -> Dict[str, Any]:
        """Get courses filtered based on user role"""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundException("User not found")
        
        query = Course.query
        
        if user.is_teacher():
            query = query.filter_by(teacher_id=user_id)
        elif user.is_student():
            query = query.filter_by(is_published=True)
        
        if category:
            query = query.filter_by(category=category)
        
        if search:
            query = query.filter(
                or_(
                    Course.title.contains(search),
                    Course.description.contains(search)
                )
            )
        
        pagination = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        courses = [course.to_dict() for course in pagination.items]
        
        if user.is_student():
            CourseService._add_enrollment_status(courses, user_id)
        
        for course in courses:
            db_course = Course.query.get(course['id'])
            course['lesson_count'] = db_course.lessons.count()
            course['quiz_count'] = db_course.quizzes.count()
            course['assignment_count'] = db_course.assignments.count()
            if db_course.teacher:
                course['teacher_name'] = f"{db_course.teacher.full_name}".strip()
                
        return {
            'courses': courses,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }
    
    @staticmethod
    def get_course(user_id: int, course_id: int) -> Dict[str, Any]:
        """Get a specific course with details"""
        user = User.query.get(user_id)
        course = Course.query.get(course_id)
        
        if not course:
            raise NotFoundException("Course not found")
        
        if not course.is_published and not user.can_access_course(course):
            raise PermissionException("Access denied")
        
        course_data = course.to_dict()
        
        if user.is_student():
            enrollment = Enrollment.query.filter_by(
                student_id=user_id, 
                course_id=course_id
            ).first()
            course_data['is_enrolled'] = enrollment is not None
            if enrollment:
                course_data['enrollment'] = enrollment.to_dict()
        
        course_data['lesson_count'] = course.lessons.count()
        course_data['quiz_count'] = course.quizzes.count()
        course_data['assignment_count'] = course.assignments.count()
        
        return course_data
    
    @staticmethod
    def create_course(teacher_id: int, course_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new course"""
        required_fields = ['title', 'description']
        for field in required_fields:
            if field not in course_data or not course_data[field]:
                raise ValidationException(f'{field} is required')
        
        start_date = None
        end_date = None
        
        if course_data.get('start_date'):
            try:
                start_date = datetime.fromisoformat(course_data['start_date'])
            except ValueError:
                raise ValidationException("Invalid start_date format")
        
        if course_data.get('end_date'):
            try:
                end_date = datetime.fromisoformat(course_data['end_date'])
            except ValueError:
                raise ValidationException("Invalid end_date format")
        
        course = Course(
            title=course_data['title'],
            description=course_data['description'],
            category=course_data.get('category'),
            teacher_id=teacher_id,
            start_date=start_date,
            end_date=end_date,
            max_students=course_data.get('max_students', 50),
            is_published=course_data.get('is_published', False)
        )
        
        db.session.add(course)
        db.session.commit()
        
        return {
            'message': 'Course created successfully',
            'course': course.to_dict()
        }
    
    @staticmethod
    def update_course(teacher_id: int, course_id: int, course_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a course"""
        course = Course.query.get(course_id)
        if not course:
            raise NotFoundException("Course not found")
        
        if course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        allowed_fields = ['title', 'description', 'category', 'max_students', 'is_published']
        for field in allowed_fields:
            if field in course_data:
                setattr(course, field, course_data[field])
        
        if 'start_date' in course_data:
            course.start_date = datetime.fromisoformat(course_data['start_date']) if course_data['start_date'] else None
        if 'end_date' in course_data:
            course.end_date = datetime.fromisoformat(course_data['end_date']) if course_data['end_date'] else None
        
        course.updated_at = datetime.utcnow()
        db.session.commit()
        
        return {
            'message': 'Course updated successfully',
            'course': course.to_dict()
        }
    
    @staticmethod
    def delete_course(teacher_id: int, course_id: int) -> Dict[str, str]:
        """Delete a course"""
        course = Course.query.get(course_id)
        if not course:
            raise NotFoundException("Course not found")
        
        if course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        active_enrollments = course.enrollments.filter_by(status='active').count()
        if active_enrollments > 0:
            raise ValidationException(f'Cannot delete course with {active_enrollments} active enrollments')
        
        db.session.delete(course)
        db.session.commit()
        
        return {'message': 'Course deleted successfully'}
    
    @staticmethod
    def enroll_student(student_id: int, course_id: int) -> Dict[str, Any]:
        """Enroll a student in a course"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise ValidationException("Only students can enroll in courses")
        
        course = Course.query.get(course_id)
        if not course:
            raise NotFoundException("Course not found")
        
        if not course.is_published:
            raise ValidationException("Course is not published")
        
        existing_enrollment = Enrollment.query.filter_by(
            student_id=student_id,
            course_id=course_id
        ).first()
        
        if existing_enrollment:
            if existing_enrollment.status == 'active':
                raise ValidationException("Already enrolled in this course")
            elif existing_enrollment.status == 'completed':
                raise ValidationException("You have already completed this course")
            elif existing_enrollment.status == 'dropped':
                existing_enrollment.status = 'active'
                existing_enrollment.enrolled_at = datetime.utcnow()
                existing_enrollment.progress_percentage = 0.0  # Reset progress
                db.session.commit()
                
                # Notify teacher about re-enrollment
                NotificationService.notify_student_enrollment(course.teacher_id, student_id, course_id)
                
                return {
                    'message': 'Re-enrolled in course successfully',
                    'enrollment': existing_enrollment.to_dict()
                }
        
        if course.is_full():
            raise ValidationException("Course is full")
        
        enrollment = Enrollment(
            student_id=student_id,
            course_id=course_id,
            status='active'
        )
        
        db.session.add(enrollment)
        db.session.commit()
        
        try:
            NotificationService.notify_student_enrollment(course.teacher_id, student_id, course_id)
        except Exception as e:
            print(f"Failed to send enrollment notification: {e}")        
        
        return {
            'message': 'Enrolled in course successfully',
            'enrollment': enrollment.to_dict()
        }
    
    @staticmethod
    def drop_course(student_id: int, course_id: int) -> Dict[str, str]:
        """Drop a course"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise ValidationException("Only students can drop courses")
        
        enrollment = Enrollment.query.filter_by(
            student_id=student_id,
            course_id=course_id,
            status='active'
        ).first()
        
        if not enrollment:
            raise NotFoundException("Not enrolled in this course")
        
        enrollment.status = 'dropped'
        db.session.commit()
        
        return {'message': 'Course dropped successfully'}
    
    @staticmethod
    def get_enrolled_courses(student_id: int, page: int = 1, per_page: int = 20, 
                        status: str = 'active') -> Dict[str, Any]:
        """Get courses the student is enrolled in - FIXED"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise ValidationException("Only students can access enrolled courses")
        
        query = Enrollment.query.filter_by(student_id=student_id)
        
        # Update enrollment progress before filtering
        all_enrollments = query.all()
        for enrollment in all_enrollments:
            current_progress = enrollment.calculate_progress()
            if enrollment.progress_percentage != current_progress:
                enrollment.progress_percentage = current_progress
                
                # Auto-complete course if progress is 100%
                if current_progress >= 100 and enrollment.status == 'active':
                    enrollment.status = 'completed'
                    enrollment.completed_at = datetime.utcnow()
        
        db.session.commit()
        
        # Now apply filters
        if status == 'active':
            query = query.filter_by(status='active')
        elif status == 'completed':
            query = query.filter_by(status='completed')
        elif status == 'all' or not status:
            query = query.filter(Enrollment.status.in_(['active', 'completed']))
        else:
            query = query.filter_by(status=status)
        
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        enrollments = []
        for enrollment in pagination.items:
            enrollment_data = enrollment.to_dict()
            course_data = enrollment.course.to_dict()
            
            course_data['lesson_count'] = enrollment.course.lessons.count()
            course_data['quiz_count'] = enrollment.course.quizzes.count()
            course_data['assignment_count'] = enrollment.course.assignments.count()
            
            if enrollment.course.teacher:
                course_data['teacher_name'] = f"{enrollment.course.teacher.full_name}".strip()
            
            enrollment_data['course'] = course_data
            enrollments.append(enrollment_data)
        
        return {
            'enrollments': enrollments,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }
    
    @staticmethod
    def get_course_students(teacher_id: int, course_id: int) -> Dict[str, Any]:
        """Get students enrolled in a course"""
        course = Course.query.get(course_id)
        if not course:
            raise NotFoundException("Course not found")
        
        if course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        enrollments = Enrollment.query.filter_by(
            course_id=course_id,
            status='active'
        ).all()
        
        students = []
        for enrollment in enrollments:
            student_data = enrollment.student.to_dict()
            student_data['enrollment'] = enrollment.to_dict()
            students.append(student_data)
        
        return {
            'students': students,
            'total': len(students)
        }
    
    @staticmethod
    def _add_enrollment_status(courses: List[Dict], student_id: int):
        """Add enrollment status to courses for students"""
        enrollments = Enrollment.query.filter_by(student_id=student_id).all()
        enrolled_course_ids = {e.course_id for e in enrollments}
        
        for course in courses:
            course['is_enrolled'] = course['id'] in enrolled_course_ids