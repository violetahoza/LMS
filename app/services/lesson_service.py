# app/services/lesson_service.py
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.models import db, User, Course, Lesson, LessonProgress, Enrollment
from app.utils.base_controller import ValidationException, PermissionException, NotFoundException

class LessonService:
    """Service for lesson-related operations"""
    
    @staticmethod
    def get_course_lessons(user_id: int, course_id: int) -> Dict[str, Any]:
        """Get all lessons for a course with user progress"""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundException("User not found")
        
        course = Course.query.get(course_id)
        if not course:
            raise NotFoundException("Course not found")
        
        if not user.can_access_course(course):
            raise PermissionException("Access denied")
        
        lessons = course.lessons.order_by(Lesson.order_number).all()
        lessons_data = []
        
        for lesson in lessons:
            lesson_dict = lesson.to_dict()
            
            if user.is_student():
                progress = LessonProgress.query.filter_by(
                    student_id=user_id,
                    lesson_id=lesson.id
                ).first()
                
                lesson_dict['progress'] = {
                    'viewed': progress is not None,
                    'completed': progress.completed_at is not None if progress else False,
                    'time_spent_minutes': progress.time_spent_minutes if progress else 0
                }
            
            lessons_data.append(lesson_dict)
        
        return {
            'lessons': lessons_data,
            'total': len(lessons_data)
        }
    
    @staticmethod
    def get_lesson(user_id: int, lesson_id: int) -> Dict[str, Any]:
        """Get a specific lesson and track view for students"""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundException("User not found")
        
        lesson = Lesson.query.get(lesson_id)
        if not lesson:
            raise NotFoundException("Lesson not found")
        
        if not user.can_access_course(lesson.course):
            raise PermissionException("Access denied")
        
        lesson_data = lesson.to_dict()
        
        if user.is_student():
            progress = LessonService._track_lesson_view(user_id, lesson_id)
            lesson_data['progress'] = {
                'viewed': True,
                'completed': progress.completed_at is not None,
                'time_spent_minutes': progress.time_spent_minutes
            }
        
        return lesson_data
    
    @staticmethod
    def create_lesson(teacher_id: int, lesson_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new lesson"""
        required_fields = ['course_id', 'title', 'content', 'order_number']
        for field in required_fields:
            if field not in lesson_data:
                raise ValidationException(f'{field} is required')
        
        course = Course.query.get(lesson_data['course_id'])
        if not course:
            raise NotFoundException("Course not found")
        
        if course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        lesson = Lesson(
            course_id=lesson_data['course_id'],
            title=lesson_data['title'],
            content=lesson_data['content'],
            order_number=lesson_data['order_number'],
            lesson_type=lesson_data.get('lesson_type', 'text'),
            video_url=lesson_data.get('video_url'),
            duration_minutes=lesson_data.get('duration_minutes')
        )
        
        db.session.add(lesson)
        db.session.commit()
        
        return {
            'message': 'Lesson created successfully',
            'lesson': lesson.to_dict()
        }
    
    @staticmethod
    def update_lesson(teacher_id: int, lesson_id: int, lesson_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a lesson"""
        lesson = Lesson.query.get(lesson_id)
        if not lesson:
            raise NotFoundException("Lesson not found")
        
        if lesson.course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        allowed_fields = ['title', 'content', 'order_number', 'lesson_type', 'video_url', 'duration_minutes']
        for field in allowed_fields:
            if field in lesson_data:
                setattr(lesson, field, lesson_data[field])
        
        lesson.updated_at = datetime.utcnow()
        db.session.commit()
        
        return {
            'message': 'Lesson updated successfully',
            'lesson': lesson.to_dict()
        }
    
    @staticmethod
    def delete_lesson(teacher_id: int, lesson_id: int) -> Dict[str, str]:
        """Delete a lesson"""
        lesson = Lesson.query.get(lesson_id)
        if not lesson:
            raise NotFoundException("Lesson not found")
        
        if lesson.course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        db.session.delete(lesson)
        db.session.commit()
        
        return {'message': 'Lesson deleted successfully'}
    
    @staticmethod
    def complete_lesson(student_id: int, lesson_id: int, time_spent_minutes: Optional[int] = None) -> Dict[str, Any]:
        """Mark a lesson as complete"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise ValidationException("Only students can complete lessons")
        
        lesson = Lesson.query.get(lesson_id)
        if not lesson:
            raise NotFoundException("Lesson not found")
        
        # Check enrollment
        enrollment = Enrollment.query.filter_by(
            student_id=student_id,
            course_id=lesson.course_id,
            status='active'
        ).first()
        
        if not enrollment:
            raise PermissionException("Not enrolled in this course")
        
        # Update or create progress
        progress = LessonProgress.query.filter_by(
            student_id=student_id,
            lesson_id=lesson_id
        ).first()
        
        if not progress:
            progress = LessonProgress(
                student_id=student_id,
                lesson_id=lesson_id
            )
            db.session.add(progress)
        
        progress.completed_at = datetime.utcnow()
        if time_spent_minutes:
            progress.time_spent_minutes = time_spent_minutes
        
        # Update course progress
        enrollment.progress_percentage = enrollment.calculate_progress()
        
        # Check if course is completed
        if LessonService._is_course_completed(student_id, lesson.course_id):
            enrollment.status = 'completed'
            enrollment.completed_at = datetime.utcnow()
        
        db.session.commit()
        
        return {
            'lesson_completed': True,
            'course_progress': enrollment.progress_percentage,
            'course_completed': enrollment.status == 'completed'
        }
    
    @staticmethod
    def _track_lesson_view(student_id: int, lesson_id: int) -> LessonProgress:
        """Track that a student viewed a lesson"""
        progress = LessonProgress.query.filter_by(
            student_id=student_id,
            lesson_id=lesson_id
        ).first()
        
        if not progress:
            progress = LessonProgress(
                student_id=student_id,
                lesson_id=lesson_id
            )
            db.session.add(progress)
        else:
            progress.viewed_at = datetime.utcnow()
        
        db.session.commit()
        return progress
    
    @staticmethod
    def _is_course_completed(student_id: int, course_id: int) -> bool:
        """Check if student has completed all lessons in course"""
        course = Course.query.get(course_id)
        total_lessons = course.lessons.count()
        
        completed_lessons = LessonProgress.query.filter_by(
            student_id=student_id
        ).join(Lesson).filter(
            Lesson.course_id == course_id,
            LessonProgress.completed_at.isnot(None)
        ).count()
        
        return completed_lessons == total_lessons