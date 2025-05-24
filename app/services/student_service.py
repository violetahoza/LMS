# app/services/student_service.py
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import desc, func
from app.models import db, User, Course, Enrollment, Lesson, Quiz, Assignment, QuizAttempt, AssignmentSubmission, LessonProgress, UserRole
from app.utils.base_controller import ValidationException, PermissionException, NotFoundException

class StudentService:
    """Service for student-related operations and progress tracking"""
    
    @staticmethod
    def get_student_dashboard(student_id: int) -> Dict[str, Any]:
        """Get student dashboard data"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise PermissionException("Only students can access this dashboard")
        
        # Get enrolled courses
        enrollments = user.enrollments.filter_by(status='active').all()
        
        # Calculate overall statistics
        total_courses = len(enrollments)
        completed_courses = user.enrollments.filter_by(status='completed').count()
        
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
        
        # Upcoming deadlines
        upcoming_assignments = []
        for enrollment in enrollments:
            assignments = Assignment.query.filter_by(course_id=enrollment.course_id).filter(
                Assignment.due_date >= datetime.utcnow(),
                Assignment.due_date <= datetime.utcnow() + timedelta(days=7)
            ).all()
            
            for assignment in assignments:
                # Check if already submitted
                submission = AssignmentSubmission.query.filter_by(
                    assignment_id=assignment.id,
                    student_id=student_id
                ).first()
                
                if not submission:
                    upcoming_assignments.append({
                        'id': assignment.id,
                        'title': assignment.title,
                        'course_title': enrollment.course.title,
                        'due_date': assignment.due_date.isoformat() if assignment.due_date else None,
                        'days_left': (assignment.due_date - datetime.utcnow()).days if assignment.due_date else None
                    })
        
        # Sort by due date
        upcoming_assignments.sort(key=lambda x: x['due_date'] if x['due_date'] else '')
        
        # Course progress
        course_progress = []
        for enrollment in enrollments[:5]:  # Top 5 courses
            progress = StudentService.calculate_course_progress(student_id, enrollment.course_id)
            course_progress.append({
                'course': enrollment.course.to_dict(),
                'progress': progress
            })
        
        return {
            'stats': {
                'total_courses': total_courses,
                'completed_courses': completed_courses,
                'completion_rate': (completed_courses / total_courses * 100) if total_courses > 0 else 0,
                'recent_lessons': recent_lessons,
                'recent_quiz_attempts': recent_quiz_attempts
            },
            'upcoming_assignments': upcoming_assignments[:5],
            'course_progress': course_progress
        }
    
    @staticmethod
    def get_student_progress(teacher_id: int, student_id: int, course_id: Optional[int] = None) -> Dict[str, Any]:
        """Get detailed student progress (for teachers)"""
        teacher = User.query.get(teacher_id)
        student = User.query.get(student_id)
        
        if not teacher or not teacher.is_teacher():
            raise PermissionException("Only teachers can access student progress")
        
        if not student or not student.is_student():
            raise NotFoundException("Student not found")
        
        if course_id:
            # Check if teacher owns the course
            course = Course.query.get(course_id)
            if not course or course.teacher_id != teacher_id:
                raise PermissionException("Access denied to this course")
            
            # Get detailed progress for specific course
            progress = StudentService.get_detailed_course_progress(student_id, course_id)
            
            return {
                'student': student.to_dict(),
                'course': course.to_dict(),
                'progress': progress
            }
        else:
            # Get progress across all teacher's courses where student is enrolled
            teacher_courses = teacher.taught_courses.all()
            course_progresses = []
            
            for course in teacher_courses:
                enrollment = Enrollment.query.filter_by(
                    student_id=student_id,
                    course_id=course.id
                ).first()
                
                if enrollment:
                    progress = StudentService.calculate_course_progress(student_id, course.id)
                    course_progresses.append({
                        'course': course.to_dict(),
                        'enrollment': enrollment.to_dict(),
                        'progress': progress
                    })
            
            return {
                'student': student.to_dict(),
                'courses': course_progresses,
                'total_courses': len(course_progresses)
            }
    
    @staticmethod
    def calculate_course_progress(student_id: int, course_id: int) -> Dict[str, Any]:
        """Calculate student progress for a specific course"""
        course = Course.query.get(course_id)
        if not course:
            raise NotFoundException("Course not found")
        
        # Lesson progress
        total_lessons = course.lessons.count()
        completed_lessons = LessonProgress.query.filter_by(
            student_id=student_id
        ).join(Lesson).filter(
            Lesson.course_id == course_id,
            LessonProgress.completed_at.isnot(None)
        ).count()
        
        viewed_lessons = LessonProgress.query.filter_by(
            student_id=student_id
        ).join(Lesson).filter(
            Lesson.course_id == course_id
        ).count()
        
        # Quiz progress
        course_quizzes = course.quizzes.all()
        quiz_scores = []
        total_quiz_score = 0
        passed_quizzes = 0
        
        for quiz in course_quizzes:
            best_attempt = QuizAttempt.query.filter_by(
                student_id=student_id,
                quiz_id=quiz.id,
                status='completed'
            ).order_by(desc(QuizAttempt.score)).first()
            
            if best_attempt:
                quiz_scores.append({
                    'quiz_id': quiz.id,
                    'quiz_title': quiz.title,
                    'score': best_attempt.score,
                    'passed': best_attempt.score >= quiz.passing_score,
                    'attempts': QuizAttempt.query.filter_by(
                        student_id=student_id,
                        quiz_id=quiz.id
                    ).count()
                })
                total_quiz_score += best_attempt.score
                if best_attempt.score >= quiz.passing_score:
                    passed_quizzes += 1
        
        # Assignment progress
        course_assignments = course.assignments.all()
        assignment_grades = []
        total_assignment_score = 0
        submitted_assignments = 0
        graded_assignments = 0
        
        for assignment in course_assignments:
            submission = AssignmentSubmission.query.filter_by(
                student_id=student_id,
                assignment_id=assignment.id
            ).first()
            
            if submission:
                submitted_assignments += 1
                assignment_data = {
                    'assignment_id': assignment.id,
                    'assignment_title': assignment.title,
                    'submitted_at': submission.submitted_at.isoformat() if submission.submitted_at else None,
                    'status': submission.status,
                    'grade': submission.grade,
                    'feedback': submission.feedback
                }
                
                if submission.grade is not None:
                    graded_assignments += 1
                    # Convert to percentage
                    percentage = (submission.grade / assignment.total_points) * 100
                    assignment_data['percentage'] = percentage
                    total_assignment_score += percentage
                
                assignment_grades.append(assignment_data)
        
        # Calculate averages
        lesson_progress_percentage = (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0
        quiz_average = (total_quiz_score / len(quiz_scores)) if quiz_scores else 0
        assignment_average = (total_assignment_score / graded_assignments) if graded_assignments > 0 else 0
        
        # Overall progress (weighted average)
        weights = {'lessons': 0.3, 'quizzes': 0.4, 'assignments': 0.3}
        overall_percentage = (
            lesson_progress_percentage * weights['lessons'] +
            quiz_average * weights['quizzes'] +
            assignment_average * weights['assignments']
        )
        
        # Time spent
        total_time_spent = db.session.query(func.sum(LessonProgress.time_spent_minutes)).filter_by(
            student_id=student_id
        ).join(Lesson).filter(
            Lesson.course_id == course_id
        ).scalar() or 0
        
        return {
            'lessons': {
                'total': total_lessons,
                'viewed': viewed_lessons,
                'completed': completed_lessons,
                'percentage': lesson_progress_percentage
            },
            'quizzes': {
                'total': len(course_quizzes),
                'attempted': len(quiz_scores),
                'passed': passed_quizzes,
                'average_score': quiz_average,
                'details': quiz_scores
            },
            'assignments': {
                'total': len(course_assignments),
                'submitted': submitted_assignments,
                'graded': graded_assignments,
                'average_score': assignment_average,
                'details': assignment_grades
            },
            'overall_percentage': overall_percentage,
            'time_spent_minutes': total_time_spent,
            'last_activity': StudentService.get_last_activity(student_id, course_id)
        }
    
    @staticmethod
    def get_detailed_course_progress(student_id: int, course_id: int) -> Dict[str, Any]:
        """Get very detailed progress including individual items"""
        basic_progress = StudentService.calculate_course_progress(student_id, course_id)
        
        course = Course.query.get(course_id)
        
        # Detailed lesson progress
        lessons_detail = []
        for lesson in course.lessons.order_by(Lesson.order_number).all():
            progress = LessonProgress.query.filter_by(
                student_id=student_id,
                lesson_id=lesson.id
            ).first()
            
            lessons_detail.append({
                'lesson': lesson.to_dict(),
                'viewed': progress is not None,
                'completed': progress.completed_at is not None if progress else False,
                'time_spent': progress.time_spent_minutes if progress else 0,
                'last_viewed': progress.viewed_at.isoformat() if progress and progress.viewed_at else None
            })
        
        # Add detailed info to basic progress
        basic_progress['detailed_lessons'] = lessons_detail
        
        return basic_progress
    
    @staticmethod
    def get_last_activity(student_id: int, course_id: int) -> Optional[str]:
        """Get student's last activity in a course"""
        # Check lesson views
        last_lesson = LessonProgress.query.filter_by(
            student_id=student_id
        ).join(Lesson).filter(
            Lesson.course_id == course_id
        ).order_by(desc(LessonProgress.viewed_at)).first()
        
        # Check quiz attempts
        last_quiz = QuizAttempt.query.filter_by(
            student_id=student_id
        ).join(Quiz).filter(
            Quiz.course_id == course_id
        ).order_by(desc(QuizAttempt.started_at)).first()
        
        # Check assignment submissions
        last_assignment = AssignmentSubmission.query.filter_by(
            student_id=student_id
        ).join(Assignment).filter(
            Assignment.course_id == course_id
        ).order_by(desc(AssignmentSubmission.submitted_at)).first()
        
        # Find most recent activity
        activities = []
        if last_lesson:
            activities.append(last_lesson.viewed_at)
        if last_quiz:
            activities.append(last_quiz.started_at)
        if last_assignment:
            activities.append(last_assignment.submitted_at)
        
        if activities:
            return max(activities).isoformat()
        
        return None


class MessageService:
    """Service for messaging between teachers and students"""
    
    @staticmethod
    def send_message(sender_id: int, recipient_id: int, subject: str, content: str, course_id: Optional[int] = None) -> Dict[str, Any]:
        """Send a message between users"""
        # Note: This is a placeholder implementation
        # In a real application, you'd have a Message model
        
        sender = User.query.get(sender_id)
        recipient = User.query.get(recipient_id)
        
        if not sender or not recipient:
            raise NotFoundException("User not found")
        
        # Validate permissions
        if course_id:
            course = Course.query.get(course_id)
            if not course:
                raise NotFoundException("Course not found")
            
            # Check if both users have access to the course
            if sender.is_teacher() and course.teacher_id != sender_id:
                raise PermissionException("Teacher does not own this course")
            
            if recipient.is_student():
                enrollment = Enrollment.query.filter_by(
                    student_id=recipient_id,
                    course_id=course_id,
                    status='active'
                ).first()
                if not enrollment:
                    raise PermissionException("Student not enrolled in this course")
        
        # For now, we'll return a success message
        # In a real implementation, you'd save to a messages table
        return {
            'message': 'Message sent successfully',
            'data': {
                'sender': sender.full_name,
                'recipient': recipient.full_name,
                'subject': subject,
                'course': course.title if course_id else None,
                'sent_at': datetime.utcnow().isoformat()
            }
        }
    
    @staticmethod
    def get_conversations(user_id: int, course_id: Optional[int] = None) -> Dict[str, Any]:
        """Get user's message conversations"""
        # Placeholder implementation
        # In a real app, you'd query actual message threads
        
        user = User.query.get(user_id)
        if not user:
            raise NotFoundException("User not found")
        
        # Return mock data for now
        conversations = []
        
        if user.is_teacher():
            # Get students from teacher's courses
            courses = user.taught_courses.all()
            if course_id:
                courses = [c for c in courses if c.id == course_id]
            
            for course in courses:
                enrollments = course.enrollments.filter_by(status='active').limit(5).all()
                for enrollment in enrollments:
                    conversations.append({
                        'id': f"conv_{course.id}_{enrollment.student_id}",
                        'participant': enrollment.student.to_dict(),
                        'course': course.to_dict(),
                        'last_message': 'Click to start conversation',
                        'last_message_at': None,
                        'unread_count': 0
                    })
        
        elif user.is_student():
            # Get teachers from enrolled courses
            enrollments = user.enrollments.filter_by(status='active').all()
            if course_id:
                enrollments = [e for e in enrollments if e.course_id == course_id]
            
            for enrollment in enrollments:
                conversations.append({
                    'id': f"conv_{enrollment.course_id}_{enrollment.course.teacher_id}",
                    'participant': enrollment.course.teacher.to_dict(),
                    'course': enrollment.course.to_dict(),
                    'last_message': 'Click to start conversation',
                    'last_message_at': None,
                    'unread_count': 0
                })
        
        return {
            'conversations': conversations,
            'total': len(conversations)
        }
    
    @staticmethod
    def create_announcement(teacher_id: int, course_id: int, title: str, content: str) -> Dict[str, Any]:
        """Create a course announcement"""
        # Placeholder implementation
        teacher = User.query.get(teacher_id)
        course = Course.query.get(course_id)
        
        if not teacher or not teacher.is_teacher():
            raise PermissionException("Only teachers can create announcements")
        
        if not course or course.teacher_id != teacher_id:
            raise PermissionException("Access denied to this course")
        
        # In a real implementation, you'd save to an announcements table
        return {
            'message': 'Announcement created successfully',
            'data': {
                'title': title,
                'content': content,
                'course': course.title,
                'created_by': teacher.full_name,
                'created_at': datetime.utcnow().isoformat()
            }
        }