# app/services/student_service.py
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import desc, func
from app.models import (
    db, User, Course, Enrollment, Lesson, LessonProgress, 
    Quiz, QuizAttempt, Assignment, AssignmentSubmission, Message
)
from app.utils.base_controller import ValidationException, PermissionException, NotFoundException
from app.utils.helpers import calculate_student_progress

class StudentService:
    """Service for student-specific operations"""
    
    @staticmethod
    def get_student_dashboard(student_id: int) -> Dict[str, Any]:
        """Get student dashboard data"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise PermissionException("Only students can access this dashboard")
        
        # Get active enrollments
        enrollments = user.enrollments.filter_by(status='active').all()
        
        # Calculate overall statistics
        total_courses = len(enrollments)
        completed_courses = len([e for e in enrollments if e.status == 'completed'])
        
        # Recent activity
        recent_lessons = LessonProgress.query.filter_by(
            student_id=student_id
        ).filter(
            LessonProgress.viewed_at >= datetime.utcnow() - timedelta(days=7)
        ).count()
        
        recent_quiz_attempts = QuizAttempt.query.filter_by(
            student_id=student_id
        ).filter(
            QuizAttempt.started_at >= datetime.utcnow() - timedelta(days=7)
        ).count()
        
        # Course progress data
        course_progress = []
        total_progress = 0
        
        for enrollment in enrollments:
            progress = calculate_student_progress(student_id, enrollment.course_id)
            course_data = {
                'course': enrollment.course.to_dict(),
                'enrollment': enrollment.to_dict(),
                'progress': progress
            }
            course_progress.append(course_data)
            total_progress += progress['overall_percentage']
        
        avg_progress = total_progress / total_courses if total_courses > 0 else 0
        
        # Upcoming assignments and quizzes
        upcoming_items = StudentService._get_upcoming_items(student_id)
        
        # Recent achievements
        recent_achievements = StudentService._get_recent_achievements(student_id)
        
        return {
            'statistics': {
                'total_courses': total_courses,
                'completed_courses': completed_courses,
                'average_progress': avg_progress,
                'recent_lessons': recent_lessons,
                'recent_quiz_attempts': recent_quiz_attempts
            },
            'course_progress': course_progress,
            'upcoming_items': upcoming_items,
            'recent_achievements': recent_achievements
        }
    
    @staticmethod
    def get_student_progress(teacher_id: Optional[int], student_id: int, course_id: Optional[int] = None) -> Dict[str, Any]:
        """Get detailed student progress"""
        student = User.query.get(student_id)
        if not student or not student.is_student():
            raise NotFoundException("Student not found")
        
        # If teacher_id is provided, verify teacher has access
        if teacher_id:
            teacher = User.query.get(teacher_id)
            if not teacher or not teacher.is_teacher():
                raise PermissionException("Only teachers can view student progress")
        
        if course_id:
            # Single course progress
            course = Course.query.get(course_id)
            if not course:
                raise NotFoundException("Course not found")
            
            # Verify teacher owns the course if teacher_id provided
            if teacher_id and course.teacher_id != teacher_id:
                raise PermissionException("Access denied to this course")
            
            # Check if student is enrolled
            enrollment = Enrollment.query.filter_by(
                student_id=student_id,
                course_id=course_id
            ).first()
            
            if not enrollment:
                raise NotFoundException("Student not enrolled in this course")
            
            progress = calculate_student_progress(student_id, course_id)
            
            # Get detailed lesson progress
            detailed_lessons = []
            for lesson in course.lessons.order_by(Lesson.order_number).all():
                lesson_progress = LessonProgress.query.filter_by(
                    student_id=student_id,
                    lesson_id=lesson.id
                ).first()
                
                detailed_lessons.append({
                    'lesson': lesson.to_dict(),
                    'viewed': lesson_progress is not None,
                    'completed': lesson_progress.completed_at is not None if lesson_progress else False,
                    'time_spent': lesson_progress.time_spent_minutes if lesson_progress else 0,
                    'last_viewed': lesson_progress.viewed_at.isoformat() if lesson_progress and lesson_progress.viewed_at else None
                })
            
            progress['detailed_lessons'] = detailed_lessons
            
            return {
                'student': student.to_dict(),
                'course': course.to_dict(),
                'enrollment': enrollment.to_dict(),
                'progress': progress
            }
        else:
            # All courses progress
            enrollments = student.enrollments.all()
            courses_progress = []
            
            for enrollment in enrollments:
                # Skip if teacher specified and doesn't own the course
                if teacher_id and enrollment.course.teacher_id != teacher_id:
                    continue
                
                progress = calculate_student_progress(student_id, enrollment.course_id)
                courses_progress.append({
                    'course': enrollment.course.to_dict(),
                    'enrollment': enrollment.to_dict(),
                    'progress': progress
                })
            
            return {
                'student': student.to_dict(),
                'courses': courses_progress
            }
    
    @staticmethod
    def _get_upcoming_items(student_id: int, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """Get upcoming assignments and quizzes"""
        upcoming = []
        cutoff_date = datetime.utcnow() + timedelta(days=days_ahead)
        
        # Get student's enrolled courses
        enrolled_course_ids = [
            e.course_id for e in Enrollment.query.filter_by(
                student_id=student_id, 
                status='active'
            ).all()
        ]
        
        # Upcoming assignments
        assignments = Assignment.query.filter(
            Assignment.course_id.in_(enrolled_course_ids),
            Assignment.due_date.isnot(None),
            Assignment.due_date >= datetime.utcnow(),
            Assignment.due_date <= cutoff_date
        ).all()
        
        for assignment in assignments:
            # Check if already submitted
            submission = AssignmentSubmission.query.filter_by(
                student_id=student_id,
                assignment_id=assignment.id
            ).first()
            
            if not submission or submission.status == 'returned':
                upcoming.append({
                    'type': 'assignment',
                    'title': assignment.title,
                    'course_title': assignment.course.title,
                    'due_date': assignment.due_date.isoformat(),
                    'days_remaining': (assignment.due_date - datetime.utcnow()).days,
                    'submitted': submission is not None
                })
        
        # Upcoming quizzes (based on course structure - this is simplified)
        # In a real implementation, you might have scheduled quizzes
        
        # Sort by due date
        upcoming.sort(key=lambda x: x['due_date'])
        
        return upcoming
    
    @staticmethod
    def _get_recent_achievements(student_id: int, days_back: int = 30) -> List[Dict[str, Any]]:
        """Get recent achievements/badges earned"""
        try:
            from app.services.achievement_service import AchievementService
            return AchievementService.get_student_achievements(student_id)['achievements'][:5]
        except ImportError:
            # If achievement service not available, return empty
            return []


class MessageService:
    """Service for messaging functionality"""
    
    @staticmethod
    def get_conversations(user_id: int, course_id: Optional[int] = None) -> Dict[str, Any]:
        """Get user's message conversations"""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundException("User not found")
        
        # Build query for messages where user is sender or recipient
        query = Message.query.filter(
            (Message.sender_id == user_id) | (Message.recipient_id == user_id)
        )
        
        if course_id:
            query = query.filter_by(course_id=course_id)
        
        messages = query.order_by(desc(Message.sent_at)).all()
        
        # Group messages into conversations
        conversations = {}
        for message in messages:
            # Determine the other party in the conversation
            other_party_id = message.recipient_id if message.sender_id == user_id else message.sender_id
            
            if other_party_id not in conversations:
                other_party = User.query.get(other_party_id)
                conversations[other_party_id] = {
                    'participant': other_party.to_dict(),
                    'messages': [],
                    'last_message_at': None,
                    'unread_count': 0
                }
            
            conversations[other_party_id]['messages'].append(message.to_dict())
            
            # Update last message time
            if not conversations[other_party_id]['last_message_at'] or message.sent_at > conversations[other_party_id]['last_message_at']:
                conversations[other_party_id]['last_message_at'] = message.sent_at
            
            # Count unread messages (messages sent to current user that are unread)
            if message.recipient_id == user_id and not message.read_at:
                conversations[other_party_id]['unread_count'] += 1
        
        # Convert to list and sort by last message time
        conversation_list = list(conversations.values())
        conversation_list.sort(key=lambda x: x['last_message_at'] or datetime.min, reverse=True)
        
        return {
            'conversations': conversation_list,
            'total': len(conversation_list)
        }
    
    @staticmethod
    def send_message(sender_id: int, recipient_id: int, subject: str, content: str, course_id: Optional[int] = None) -> Dict[str, Any]:
        """Send a message"""
        sender = User.query.get(sender_id)
        recipient = User.query.get(recipient_id)
        
        if not sender:
            raise NotFoundException("Sender not found")
        
        if not recipient:
            raise NotFoundException("Recipient not found")
        
        if sender_id == recipient_id:
            raise ValidationException("Cannot send message to yourself")
        
        # Validate course if specified
        if course_id:
            course = Course.query.get(course_id)
            if not course:
                raise NotFoundException("Course not found")
            
            # Check if both users have access to the course
            sender_has_access = (
                sender.is_teacher() and course.teacher_id == sender_id
            ) or (
                sender.is_student() and Enrollment.query.filter_by(
                    student_id=sender_id, 
                    course_id=course_id,
                    status='active'
                ).first()
            )
            
            recipient_has_access = (
                recipient.is_teacher() and course.teacher_id == recipient_id
            ) or (
                recipient.is_student() and Enrollment.query.filter_by(
                    student_id=recipient_id,
                    course_id=course_id,
                    status='active'
                ).first()
            )
            
            if not (sender_has_access and recipient_has_access):
                raise PermissionException("Both users must have access to the specified course")
        
        message = Message(
            sender_id=sender_id,
            recipient_id=recipient_id,
            subject=subject.strip(),
            content=content.strip(),
            course_id=course_id
        )
        
        db.session.add(message)
        db.session.commit()
        
        return {
            'message': 'Message sent successfully',
            'message_data': message.to_dict()
        }
    
    @staticmethod
    def mark_message_read(user_id: int, message_id: int) -> Dict[str, str]:
        """Mark a message as read"""
        message = Message.query.get(message_id)
        if not message:
            raise NotFoundException("Message not found")
        
        if message.recipient_id != user_id:
            raise PermissionException("Can only mark your own received messages as read")
        
        if not message.read_at:
            message.read_at = datetime.utcnow()
            db.session.commit()
        
        return {'message': 'Message marked as read'}
    
    @staticmethod
    def create_announcement(teacher_id: int, course_id: int, title: str, content: str) -> Dict[str, Any]:
        """Create a course announcement (sent to all enrolled students)"""
        teacher = User.query.get(teacher_id)
        if not teacher or not teacher.is_teacher():
            raise PermissionException("Only teachers can create announcements")
        
        course = Course.query.get(course_id)
        if not course:
            raise NotFoundException("Course not found")
        
        if course.teacher_id != teacher_id:
            raise PermissionException("Can only create announcements for your own courses")
        
        # Get all enrolled students
        enrollments = course.enrollments.filter_by(status='active').all()
        
        if not enrollments:
            raise ValidationException("No students enrolled in this course")
        
        messages_created = 0
        
        # Send message to each enrolled student
        for enrollment in enrollments:
            message = Message(
                sender_id=teacher_id,
                recipient_id=enrollment.student_id,
                subject=f"[{course.title}] {title}",
                content=content.strip(),
                course_id=course_id,
                is_announcement=True
            )
            db.session.add(message)
            messages_created += 1
        
        db.session.commit()
        
        return {
            'message': f'Announcement sent to {messages_created} students',
            'recipients': messages_created
        }