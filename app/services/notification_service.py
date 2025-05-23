from datetime import datetime
from typing import List, Dict, Any
from abc import ABC, abstractmethod

from app.models import db, User, Course, Assignment, Quiz

class NotificationObserver(ABC):
    """Abstract base class for notification observers (Observer Pattern)"""
    
    @abstractmethod
    def notify(self, event_type: str, data: Dict[str, Any]) -> None:
        pass

class EmailNotificationObserver(NotificationObserver):
    """Email notification observer"""
    
    def notify(self, event_type: str, data: Dict[str, Any]) -> None:
        # In a real implementation, this would send actual emails
        print(f"[EMAIL] {event_type}: {data}")

class InAppNotificationObserver(NotificationObserver):
    """In-app notification observer"""
    
    def notify(self, event_type: str, data: Dict[str, Any]) -> None:
        # Store notification in database for in-app display
        print(f"[IN-APP] {event_type}: {data}")

class NotificationService:
    """Notification service implementing Observer Pattern"""
    
    def __init__(self):
        self._observers: List[NotificationObserver] = []
        self._setup_default_observers()
    
    def _setup_default_observers(self):
        """Setup default notification observers"""
        self.add_observer(EmailNotificationObserver())
        self.add_observer(InAppNotificationObserver())
    
    def add_observer(self, observer: NotificationObserver) -> None:
        """Add a notification observer"""
        if observer not in self._observers:
            self._observers.append(observer)
    
    def remove_observer(self, observer: NotificationObserver) -> None:
        """Remove a notification observer"""
        if observer in self._observers:
            self._observers.remove(observer)
    
    def notify_observers(self, event_type: str, data: Dict[str, Any]) -> None:
        """Notify all observers of an event"""
        for observer in self._observers:
            try:
                observer.notify(event_type, data)
            except Exception as e:
                print(f"Error notifying observer: {e}")
    
    def notify_assignment_due(self, assignment_id: int) -> None:
        """Notify students about assignment due date"""
        assignment = Assignment.query.get(assignment_id)
        if not assignment:
            return
        
        # Get enrolled students
        from app.models import Enrollment
        enrollments = Enrollment.query.filter_by(
            course_id=assignment.course_id,
            status='active'
        ).all()
        
        for enrollment in enrollments:
            data = {
                'student_id': enrollment.student_id,
                'student_name': enrollment.student.full_name,
                'student_email': enrollment.student.email,
                'assignment_title': assignment.title,
                'course_title': assignment.course.title,
                'due_date': assignment.due_date.isoformat() if assignment.due_date else None,
                'message': f"Assignment '{assignment.title}' is due soon!"
            }
            self.notify_observers('assignment_due', data)
    
    def notify_quiz_result(self, student_id: int, quiz_id: int, score: float) -> None:
        """Notify student about quiz result"""
        student = User.query.get(student_id)
        quiz = Quiz.query.get(quiz_id)
        
        if not student or not quiz:
            return
        
        data = {
            'student_id': student_id,
            'student_name': student.full_name,
            'student_email': student.email,
            'quiz_title': quiz.title,
            'course_title': quiz.course.title,
            'score': score,
            'passed': score >= quiz.passing_score,
            'message': f"Quiz result: {score}% on '{quiz.title}'"
        }
        self.notify_observers('quiz_result', data)
    
    def notify_course_enrollment(self, student_id: int, course_id: int) -> None:
        """Notify about new course enrollment"""
        student = User.query.get(student_id)
        course = Course.query.get(course_id)
        
        if not student or not course:
            return
        
        # Notify student
        student_data = {
            'student_id': student_id,
            'student_name': student.full_name,
            'student_email': student.email,
            'course_title': course.title,
            'teacher_name': course.teacher.full_name,
            'message': f"Successfully enrolled in '{course.title}'"
        }
        self.notify_observers('enrollment_confirmation', student_data)
        
        # Notify teacher
        teacher_data = {
            'teacher_id': course.teacher_id,
            'teacher_name': course.teacher.full_name,
            'teacher_email': course.teacher.email,
            'student_name': student.full_name,
            'course_title': course.title,
            'message': f"New enrollment: {student.full_name} joined '{course.title}'"
        }
        self.notify_observers('new_enrollment', teacher_data)
    
    def notify_assignment_submission(self, student_id: int, assignment_id: int) -> None:
        """Notify teacher about assignment submission"""
        from app.models import AssignmentSubmission
        assignment = Assignment.query.get(assignment_id)
        student = User.query.get(student_id)
        
        if not assignment or not student:
            return
        
        data = {
            'teacher_id': assignment.course.teacher_id,
            'teacher_name': assignment.course.teacher.full_name,
            'teacher_email': assignment.course.teacher.email,
            'student_name': student.full_name,
            'assignment_title': assignment.title,
            'course_title': assignment.course.title,
            'message': f"New submission: {student.full_name} submitted '{assignment.title}'"
        }
        self.notify_observers('assignment_submission', data)
    
    def notify_course_completion(self, student_id: int, course_id: int) -> None:
        """Notify about course completion"""
        student = User.query.get(student_id)
        course = Course.query.get(course_id)
        
        if not student or not course:
            return
        
        # Notify student
        student_data = {
            'student_id': student_id,
            'student_name': student.full_name,
            'student_email': student.email,
            'course_title': course.title,
            'message': f"Congratulations! You completed '{course.title}'"
        }
        self.notify_observers('course_completion', student_data)
        
        # Notify teacher
        teacher_data = {
            'teacher_id': course.teacher_id,
            'teacher_name': course.teacher.full_name,
            'teacher_email': course.teacher.email,
            'student_name': student.full_name,
            'course_title': course.title,
            'message': f"Student completed course: {student.full_name} finished '{course.title}'"
        }
        self.notify_observers('student_completion', teacher_data)

# Global notification service instance (Singleton Pattern)
notification_service = NotificationService()