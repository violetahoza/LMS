from typing import Dict, Any, List, Optional
from datetime import datetime
from app.models import Assignment, Quiz, db, User, Notification, NotificationType, NotificationPriority
from app.utils.base_controller import ValidationException, PermissionException, NotFoundException
from sqlalchemy import desc, or_

class NotificationService:
    """Service for managing notifications"""
    
    @staticmethod
    def create_notification(
        recipient_id: int,
        notification_type: NotificationType,
        title: str,
        message: str,
        sender_id: Optional[int] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        action_url: Optional[str] = None,
        related_id: Optional[int] = None
    ) -> Notification:
        """Create a new notification"""

        if isinstance(priority, NotificationPriority):
            priority_value = priority.value  
        else:
            priority_value = str(priority)

        notification = Notification(
            recipient_id=recipient_id,
            sender_id=sender_id,
            type=notification_type.value,
            priority=priority_value,
            title=title,
            message=message,
            action_url=action_url,
            related_id=related_id
        )
        
        db.session.add(notification)
        db.session.commit()
        return notification
    
    @staticmethod
    def get_user_notifications(
        user_id: int, 
        page: int = 1, 
        per_page: int = 20,
        unread_only: bool = False
    ) -> Dict[str, Any]:
        """Get notifications for a user"""
        query = Notification.query.filter_by(recipient_id=user_id)
        
        if unread_only:
            query = query.filter_by(is_read=False)
        
        query = query.order_by(desc(Notification.created_at))
        
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        notifications = [notification.to_dict() for notification in pagination.items]
        unread_count = Notification.query.filter_by(
            recipient_id=user_id,
            is_read=False
        ).count()
        
        return {
            'notifications': notifications,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages,
            'unread_count': unread_count
        }
    
    @staticmethod
    def mark_as_read(user_id: int, notification_id: int) -> Dict[str, str]:
        """Mark a notification as read"""
        notification = Notification.query.get(notification_id)
        if not notification:
            raise NotFoundException("Notification not found")
        
        if notification.recipient_id != user_id:
            raise PermissionException("Access denied")
        
        notification.mark_as_read()
        return {'message': 'Notification marked as read'}
    
    @staticmethod
    def mark_all_as_read(user_id: int) -> Dict[str, str]:
        """Mark all notifications as read for a user"""
        notifications = Notification.query.filter_by(
            recipient_id=user_id,
            is_read=False
        ).all()
        
        for notification in notifications:
            notification.mark_as_read()
        
        return {'message': f'{len(notifications)} notifications marked as read'}
    
    @staticmethod
    def delete_notification(user_id: int, notification_id: int) -> Dict[str, str]:
        """Delete a notification"""
        notification = Notification.query.get(notification_id)
        if not notification:
            raise NotFoundException("Notification not found")
        
        if notification.recipient_id != user_id:
            raise PermissionException("Access denied")
        
        db.session.delete(notification)
        db.session.commit()
        
        return {'message': 'Notification deleted'}
    
    @staticmethod
    def bulk_delete_notifications(user_id: int, notification_ids: List[int]) -> Dict[str, str]:
        """Delete multiple notifications"""
        notifications = Notification.query.filter(
            Notification.id.in_(notification_ids),
            Notification.recipient_id == user_id
        ).all()
        
        if not notifications:
            raise NotFoundException("No notifications found")
        
        for notification in notifications:
            db.session.delete(notification)
        
        db.session.commit()
        return {'message': f'{len(notifications)} notifications deleted'}
    
    @staticmethod
    def get_notification_preferences(user_id: int) -> Dict[str, Any]:
        """Get user notification preferences (placeholder for future implementation)"""
        # This would typically fetch from a user_preferences table
        return {
            'email_notifications': True,
            'push_notifications': True,
            'notification_types': {
                'messages': True,
                'enrollments': True,
                'assignments': True,
                'quizzes': True,
                'achievements': True,
                'certificates': True
            }
        }

    @staticmethod
    def notify_new_message(sender_id: int, recipient_id: int, subject: str):
        """Notify user about new message"""
        sender = User.query.get(sender_id)
        return NotificationService.create_notification(
            recipient_id=recipient_id,
            sender_id=sender_id,
            notification_type=NotificationType.MESSAGE,
            title="New Message",
            message=f"You have a new message from {sender.full_name}: {subject}",
            action_url="/messages",
            priority=NotificationPriority.NORMAL
        )
    
    @staticmethod
    def notify_student_enrollment(teacher_id: int, student_id: int, course_id: int):
        """Notify teacher about student enrollment"""
        from app.models import Course
        student = User.query.get(student_id)
        course = Course.query.get(course_id)
        
        return NotificationService.create_notification(
            recipient_id=teacher_id,
            sender_id=student_id,
            notification_type=NotificationType.ENROLLMENT,
            title="New Student Enrollment",
            message=f"{student.full_name} has enrolled in your course '{course.title}'",
            action_url=f"/teacher/courses/{course_id}/students",
            related_id=course_id
        )
    
    @staticmethod
    def notify_assignment_submission(teacher_id: int, student_id: int, assignment_id: int):
        """Notify teacher about assignment submission"""
        from app.models import Assignment
        student = User.query.get(student_id)
        assignment = Assignment.query.get(assignment_id)
        
        return NotificationService.create_notification(
            recipient_id=teacher_id,
            sender_id=student_id,
            notification_type=NotificationType.ASSIGNMENT_SUBMISSION,
            title="New Assignment Submission",
            message=f"{student.full_name} has submitted '{assignment.title}'",
            action_url=f"/teacher/assignment/{assignment_id}/submissions",
            related_id=assignment_id,
            priority=NotificationPriority.HIGH
        )
    
    @staticmethod
    def notify_assignment_graded(student_id: int, teacher_id: int, assignment_id: int, grade: float):
        """Notify student about graded assignment"""
        from app.models import Assignment
        teacher = User.query.get(teacher_id)
        assignment = Assignment.query.get(assignment_id)
        
        return NotificationService.create_notification(
            recipient_id=student_id,
            sender_id=teacher_id,
            notification_type=NotificationType.ASSIGNMENT_GRADED,
            title="Assignment Graded",
            message=f"Your assignment '{assignment.title}' has been graded by {teacher.full_name}. Grade: {grade}%",
            action_url=f"/student/courses/{assignment.course_id}/assignment/{assignment_id}",
            related_id=assignment_id
        )
    
    @staticmethod
    def notify_quiz_submission(teacher_id: int, student_id: int, quiz_id: int, score: float):
        """Notify teacher about quiz submission"""
        from app.models import Quiz
        student = User.query.get(student_id)
        quiz = Quiz.query.get(quiz_id)
        
        return NotificationService.create_notification(
            recipient_id=teacher_id,
            sender_id=student_id,
            notification_type=NotificationType.QUIZ_SUBMISSION,
            title="New Quiz Submission",
            message=f"{student.full_name} completed '{quiz.title}' with score: {score}%",
            action_url=f"/teacher/quiz/{quiz_id}/analytics",
            related_id=quiz_id
        )
    
    @staticmethod
    def notify_quiz_graded(student_id: int, teacher_id: int, quiz_id: int, score: float):
        """Notify student about graded quiz (for manual grading)"""
        from app.models import Quiz
        teacher = User.query.get(teacher_id)
        quiz = Quiz.query.get(quiz_id)
        
        return NotificationService.create_notification(
            recipient_id=student_id,
            sender_id=teacher_id,
            notification_type=NotificationType.QUIZ_GRADED,
            title="Quiz Graded",
            message=f"Your quiz '{quiz.title}' has been reviewed by {teacher.full_name}. Final Score: {score}%",
            action_url=f"/student/courses/{quiz.course_id}/quiz/{quiz_id}",
            related_id=quiz_id
        )
    
    @staticmethod
    def notify_course_completion(teacher_id: int, student_id: int, course_id: int):
        """Notify teacher about student course completion"""
        from app.models import Course
        student = User.query.get(student_id)
        course = Course.query.get(course_id)
        
        return NotificationService.create_notification(
            recipient_id=teacher_id,
            sender_id=student_id,
            notification_type=NotificationType.COURSE_COMPLETION,
            title="Student Completed Course",
            message=f"{student.full_name} has completed the course '{course.title}'",
            action_url=f"/teacher/courses/{course_id}/students",
            related_id=course_id,
            priority=NotificationPriority.HIGH
        )
    
    @staticmethod
    def notify_new_content(student_ids: List[int], teacher_id: int, course_id: int, content_type: str, content_title: str):
        """Notify students about new course content"""
        from app.models import Course
        teacher = User.query.get(teacher_id)
        course = Course.query.get(course_id)
        
        notifications = []
        for student_id in student_ids:
            notification = NotificationService.create_notification(
                recipient_id=student_id,
                sender_id=teacher_id,
                notification_type=NotificationType.NEW_CONTENT,
                title=f"New {content_type.title()} Added",
                message=f"{teacher.full_name} added a new {content_type} '{content_title}' to '{course.title}'",
                action_url=f"/student/courses/{course_id}",
                related_id=course_id
            )
            notifications.append(notification)
        
        return notifications
    
    @staticmethod
    def notify_achievement_earned(student_id: int, achievement_name: str, points: int):
        """Notify student about achievement earned"""
        return NotificationService.create_notification(
            recipient_id=student_id,
            notification_type=NotificationType.ACHIEVEMENT_EARNED,
            title="Achievement Unlocked!",
            message=f"Congratulations! You've earned the '{achievement_name}' achievement (+{points} points)",
            action_url="/student/achievements",
            priority=NotificationPriority.HIGH
        )
    
    @staticmethod
    def notify_assignment_returned(student_id, teacher_id, assignment_id, feedback):
        from app.models import Notification, NotificationType, NotificationPriority

        assignment = Assignment.query.get(assignment_id)
        if not assignment:
            return

        message = f"Your submission for '{assignment.title}' was returned for revision."
        NotificationService._send_notification(
            recipient_id=student_id,
            sender_id=teacher_id,
            type=NotificationType.ASSIGNMENT_GRADED,
            priority=NotificationPriority.NORMAL,
            title="Assignment Returned",
            message=message,
            related_id=assignment_id
        )

    @staticmethod
    def notify_quiz_graded(student_id: int, teacher_id: int, quiz_id: int, score: float):
        """Notify student when their quiz has been graded"""
        try:
            from app.models import Quiz, User
            
            quiz = Quiz.query.get(quiz_id)
            teacher = User.query.get(teacher_id)
            
            if not quiz or not teacher:
                return
            
            passed = score >= quiz.passing_score
            status_text = "passed" if passed else "needs improvement"
            
            notification = Notification(
                recipient_id=student_id,
                sender_id=teacher_id,
                type=NotificationType.QUIZ_GRADED,
                priority=NotificationPriority.HIGH if passed else NotificationPriority.NORMAL,
                title=f"Quiz Graded: {quiz.title}",
                message=f"Your quiz '{quiz.title}' has been graded by {teacher.full_name}. Score: {score:.1f}% ({status_text})",
                action_url=f"/student/quiz/{quiz_id}/results"
            )
            
            db.session.add(notification)
            db.session.commit()
            
        except Exception as e:
            print(f"Error sending quiz graded notification: {e}")

    @staticmethod
    def notify_certificate_request_submitted(student_id: int, course_id: int):
        """Notify admins about new certificate request"""
        from app.models import Course, User, UserRole
        
        student = User.query.get(student_id)
        course = Course.query.get(course_id)
        
        if not student or not course:
            return
        
        admins = User.query.filter_by(role=UserRole.ADMIN, is_active=True).all()
        
        notifications = []
        for admin in admins:
            notification = NotificationService.create_notification(
                recipient_id=admin.id,
                sender_id=student_id,
                notification_type=NotificationType.CERTIFICATE_REQUEST,
                title="New Certificate Request",
                message=f"{student.full_name} has requested a certificate for '{course.title}'",
                action_url="/admin/certificates",
                related_id=course_id,
                priority=NotificationPriority.HIGH
            )
            notifications.append(notification)
        
        return notifications

    @staticmethod
    def notify_certificate_request_resubmitted(student_id: int, course_id: int):
        """Notify admins about resubmitted certificate request"""
        from app.models import Course, User, UserRole
        
        student = User.query.get(student_id)
        course = Course.query.get(course_id)
        
        if not student or not course:
            return
        
        admins = User.query.filter_by(role=UserRole.ADMIN, is_active=True).all()
        
        notifications = []
        for admin in admins:
            notification = NotificationService.create_notification(
                recipient_id=admin.id,
                sender_id=student_id,
                notification_type=NotificationType.CERTIFICATE_REQUEST,
                title="Certificate Request Resubmitted",
                message=f"{student.full_name} has resubmitted their certificate request for '{course.title}'",
                action_url="/admin/certificates",
                related_id=course_id,
                priority=NotificationPriority.HIGH
            )
            notifications.append(notification)
        
        return notifications

    @staticmethod
    def notify_certificate_request_approved(student_id: int, course_id: int, certificate_code: str):
        """Notify student about approved certificate request"""
        from app.models import Course
        
        course = Course.query.get(course_id)
        
        if not course:
            return
        
        return NotificationService.create_notification(
            recipient_id=student_id,
            notification_type=NotificationType.CERTIFICATE_APPROVED,
            title="Certificate Request Approved",
            message=f"Your certificate request for '{course.title}' has been approved and issued! Certificate ID: {certificate_code}",
            action_url="/student/certificates",
            related_id=course_id,
            priority=NotificationPriority.HIGH
        )

    @staticmethod
    def notify_certificate_request_rejected(student_id: int, course_id: int, reason: str):
        """Notify student about rejected certificate request"""
        from app.models import Course
        
        course = Course.query.get(course_id)
        
        if not course:
            return
        
        return NotificationService.create_notification(
            recipient_id=student_id,
            notification_type=NotificationType.CERTIFICATE_REJECTED,
            title="Certificate Request Rejected",
            message=f"Your certificate request for '{course.title}' has been rejected. Reason: {reason}",
            action_url="/student/certificates",
            related_id=course_id,
            priority=NotificationPriority.NORMAL
        )

    @staticmethod
    def notify_certificate_issued(student_id: int, course_id: int, certificate_code: str):
        """Notify student about certificate issuance"""
        from app.models import Course
        course = Course.query.get(course_id)
        
        return NotificationService.create_notification(
            recipient_id=student_id,
            notification_type=NotificationType.CERTIFICATE_ISSUED,
            title="Certificate Issued",
            message=f"Your certificate for '{course.title}' has been issued! Certificate ID: {certificate_code}",
            action_url="/student/certificates",
            related_id=course_id,
            priority=NotificationPriority.HIGH
        )
    
    