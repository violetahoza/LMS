from datetime import datetime
from typing import List, Dict, Any, Optional
from app.models import AssignmentSubmission, QuizAttempt, db, User, Course, Lesson, LessonProgress, Enrollment
from app.utils.base_controller import ValidationException, PermissionException, NotFoundException
from app.services.notification_service import NotificationService

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
                    'time_spent_minutes': progress.time_spent_minutes if progress else 0,
                    'last_viewed': progress.viewed_at.isoformat() if progress and progress.viewed_at else None
                }
            
            elif user.is_teacher() and course.teacher_id == user_id:
                total_students = course.enrollments.filter_by(status='active').count()
                views = LessonProgress.query.filter_by(lesson_id=lesson.id).count()
                completions = LessonProgress.query.filter_by(
                    lesson_id=lesson.id
                ).filter(LessonProgress.completed_at.isnot(None)).count()
                
                lesson_dict['engagement'] = {
                    'total_students': total_students,
                    'views': views,
                    'completions': completions,
                    'view_rate': (views / total_students * 100) if total_students > 0 else 0,
                    'completion_rate': (completions / total_students * 100) if total_students > 0 else 0
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
                'time_spent_minutes': progress.time_spent_minutes,
                'last_viewed': progress.viewed_at.isoformat() if progress.viewed_at else None
            }
            
            if lesson.order_number > 1:
                previous_lesson = Lesson.query.filter_by(
                    course_id=lesson.course_id,
                    order_number=lesson.order_number - 1
                ).first()
                
                if previous_lesson:
                    prev_progress = LessonProgress.query.filter_by(
                        student_id=user_id,
                        lesson_id=previous_lesson.id
                    ).first()
                    
                    lesson_data['prerequisites_met'] = prev_progress is not None
                else:
                    lesson_data['prerequisites_met'] = True
            else:
                lesson_data['prerequisites_met'] = True
        
        return lesson_data
    
    @staticmethod
    def create_lesson(teacher_id: int, lesson_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new lesson"""
        required_fields = ['course_id', 'title', 'content', 'order_number']
        for field in required_fields:
            if field not in lesson_data or not lesson_data[field]:
                raise ValidationException(f'{field} is required')
        
        course = Course.query.get(lesson_data['course_id'])
        if not course:
            raise NotFoundException("Course not found")
        
        if course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        order_number = lesson_data['order_number']
        if order_number < 1:
            raise ValidationException("Order number must be positive")
        
        existing_lesson = Lesson.query.filter_by(
            course_id=lesson_data['course_id'],
            order_number=order_number
        ).first()
        
        if existing_lesson:
            lessons_to_shift = Lesson.query.filter(
                Lesson.course_id == lesson_data['course_id'],
                Lesson.order_number >= order_number
            ).all()
            
            for lesson in lessons_to_shift:
                lesson.order_number += 1
        
        lesson_type = lesson_data.get('lesson_type', 'text')
        video_url = lesson_data.get('video_url')
        
        if lesson_type in ['video', 'mixed'] and not video_url:
            raise ValidationException(f"Video URL is required for {lesson_type} lessons")
        
        if lesson_type == 'text' and video_url:
            lesson_data['video_url'] = None  # Clear video URL for text-only lessons
        
        lesson = Lesson(
            course_id=lesson_data['course_id'],
            title=lesson_data['title'].strip(),
            content=lesson_data['content'].strip(),
            order_number=order_number,
            lesson_type=lesson_type,
            video_url=video_url.strip() if video_url else None,
            duration_minutes=lesson_data.get('duration_minutes')
        )
        
        db.session.add(lesson)
        db.session.commit()
        
        course = Course.query.get(lesson_data['course_id'])
        enrolled_students = [enrollment.student_id for enrollment in course.enrollments.filter_by(status='active')]
        
        if enrolled_students:
            NotificationService.notify_new_content(
                student_ids=enrolled_students,
                teacher_id=teacher_id,
                course_id=course.id,
                content_type='lesson',
                content_title=lesson.title
            )

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
        
        if 'order_number' in lesson_data:
            new_order = lesson_data['order_number']
            if new_order < 1:
                raise ValidationException("Order number must be positive")
            
            if new_order != lesson.order_number:
                LessonService._reorder_lessons(lesson.course_id, lesson.order_number, new_order)
        
        if 'lesson_type' in lesson_data:
            lesson_type = lesson_data['lesson_type']
            video_url = lesson_data.get('video_url', lesson.video_url)
            
            if lesson_type in ['video', 'mixed'] and not video_url:
                raise ValidationException(f"Video URL is required for {lesson_type} lessons")
            
            if lesson_type == 'text':
                lesson_data['video_url'] = None  
        
        allowed_fields = ['title', 'content', 'order_number', 'lesson_type', 'video_url', 'duration_minutes']
        for field in allowed_fields:
            if field in lesson_data:
                value = lesson_data[field]
                if field in ['title', 'content'] and value:
                    value = value.strip()
                elif field == 'video_url' and value:
                    value = value.strip()
                setattr(lesson, field, value)
        
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
        
        progress_count = LessonProgress.query.filter_by(lesson_id=lesson_id).count()
        if progress_count > 0:
            raise ValidationException(f'Cannot delete lesson with {progress_count} student views')
        
        course_id = lesson.course_id
        order_number = lesson.order_number
        
        db.session.delete(lesson)
        
        lessons_to_shift = Lesson.query.filter(
            Lesson.course_id == course_id,
            Lesson.order_number > order_number
        ).all()
        
        for lesson in lessons_to_shift:
            lesson.order_number -= 1
        
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
        
        enrollment = Enrollment.query.filter_by(
            student_id=student_id,
            course_id=lesson.course_id
        ).filter(Enrollment.status.in_(['active', 'completed'])).first()
        
        if not enrollment:
            raise PermissionException("Not enrolled in this course")
        
        if lesson.order_number > 1:
            previous_lesson = Lesson.query.filter_by(
                course_id=lesson.course_id,
                order_number=lesson.order_number - 1
            ).first()
            
            if previous_lesson:
                prev_progress = LessonProgress.query.filter_by(
                    student_id=student_id,
                    lesson_id=previous_lesson.id
                ).first()
                
                if not prev_progress:
                    raise ValidationException("Previous lesson must be viewed first")
        
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
        if time_spent_minutes and time_spent_minutes > 0:
            progress.time_spent_minutes = time_spent_minutes
        
        enrollment.progress_percentage = enrollment.calculate_progress()
        
        course_completed = LessonService._is_course_fully_completed(student_id, lesson.course_id)
        
        if course_completed and enrollment.status == 'active':
            enrollment.status = 'completed'
            enrollment.completed_at = datetime.utcnow()

            NotificationService.notify_course_completion(
                teacher_id=lesson.course.teacher_id,
                student_id=student_id,
                course_id=lesson.course_id
            )
            
        db.session.commit()
        
        return {
            'message': 'Lesson completed successfully',
            'lesson_completed': True,
            'course_progress': enrollment.progress_percentage,
            'course_completed': enrollment.status == 'completed'
        }
    
    @staticmethod
    def _is_course_fully_completed(student_id: int, course_id: int) -> bool:
        """Check if student has completed ALL course requirements (lessons, quizzes, assignments)"""
        course = Course.query.get(course_id)
        
        total_lessons = course.lessons.count()
        if total_lessons > 0:
            completed_lessons = LessonProgress.query.filter_by(
                student_id=student_id
            ).join(Lesson).filter(
                Lesson.course_id == course_id,
                LessonProgress.completed_at.isnot(None)
            ).count()
            
            if completed_lessons < total_lessons:
                return False
        
        course_quizzes = course.quizzes.all()
        for quiz in course_quizzes:
            best_attempt = QuizAttempt.query.filter_by(
                student_id=student_id,
                quiz_id=quiz.id,
                status='completed'
            ).order_by(QuizAttempt.score.desc()).first()
            
            if not best_attempt or best_attempt.score < quiz.passing_score:
                return False
        
        course_assignments = course.assignments.all()
        for assignment in course_assignments:
            submission = AssignmentSubmission.query.filter_by(
                student_id=student_id,
                assignment_id=assignment.id
            ).first()
            
            if not submission or submission.status not in ['submitted', 'graded']:
                return False
        
        return True
    
    @staticmethod
    def get_lesson_analytics(teacher_id: int, lesson_id: int) -> Dict[str, Any]:
        """Get detailed analytics for a lesson"""
        lesson = Lesson.query.get(lesson_id)
        if not lesson:
            raise NotFoundException("Lesson not found")
        
        if lesson.course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        progress_records = LessonProgress.query.filter_by(lesson_id=lesson_id).all()
        
        total_enrolled = lesson.course.enrollments.filter_by(status='active').count()
        total_views = len(progress_records)
        total_completions = len([p for p in progress_records if p.completed_at])
        
        time_spent_data = [p.time_spent_minutes for p in progress_records if p.time_spent_minutes > 0]
        avg_time_spent = sum(time_spent_data) / len(time_spent_data) if time_spent_data else 0
        
        completion_timeline = []
        for progress in progress_records:
            if progress.completed_at:
                completion_timeline.append({
                    'student_name': progress.student.full_name,
                    'completed_at': progress.completed_at.isoformat(),
                    'time_spent': progress.time_spent_minutes
                })
        
        completion_timeline.sort(key=lambda x: x['completed_at'])
        
        return {
            'lesson': lesson.to_dict(),
            'statistics': {
                'total_enrolled': total_enrolled,
                'total_views': total_views,
                'total_completions': total_completions,
                'view_rate': (total_views / total_enrolled * 100) if total_enrolled > 0 else 0,
                'completion_rate': (total_completions / total_enrolled * 100) if total_enrolled > 0 else 0,
                'average_time_spent': avg_time_spent
            },
            'completion_timeline': completion_timeline
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
        
        if total_lessons == 0:
            return True
        
        completed_lessons = LessonProgress.query.filter_by(
            student_id=student_id
        ).join(Lesson).filter(
            Lesson.course_id == course_id,
            LessonProgress.completed_at.isnot(None)
        ).count()
        
        return completed_lessons == total_lessons
    
    @staticmethod
    def _reorder_lessons(course_id: int, old_order: int, new_order: int):
        """Reorder lessons when order number changes"""
        if old_order == new_order:
            return
        
        if old_order < new_order:
            lessons_to_shift = Lesson.query.filter(
                Lesson.course_id == course_id,
                Lesson.order_number > old_order,
                Lesson.order_number <= new_order
            ).all()
            
            for lesson in lessons_to_shift:
                lesson.order_number -= 1
        else:
            lessons_to_shift = Lesson.query.filter(
                Lesson.course_id == course_id,
                Lesson.order_number >= new_order,
                Lesson.order_number < old_order
            ).all()
            
            for lesson in lessons_to_shift:
                lesson.order_number += 1
    
    @staticmethod
    def duplicate_lesson(teacher_id: int, lesson_id: int) -> Dict[str, Any]:
        """Duplicate an existing lesson"""
        lesson = Lesson.query.get(lesson_id)
        if not lesson:
            raise NotFoundException("Lesson not found")
        
        if lesson.course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        max_order = db.session.query(db.func.max(Lesson.order_number)).filter_by(
            course_id=lesson.course_id
        ).scalar() or 0
        
        new_lesson = Lesson(
            course_id=lesson.course_id,
            title=f"{lesson.title} (Copy)",
            content=lesson.content,
            order_number=max_order + 1,
            lesson_type=lesson.lesson_type,
            video_url=lesson.video_url,
            duration_minutes=lesson.duration_minutes
        )
        
        db.session.add(new_lesson)
        db.session.commit()
        
        return {
            'message': 'Lesson duplicated successfully',
            'lesson': new_lesson.to_dict()
        }