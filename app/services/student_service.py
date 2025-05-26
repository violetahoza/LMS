from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy import desc, func
from app.models import db, User, Enrollment, LessonProgress, QuizAttempt, AssignmentSubmission, Certificate, Assignment
from app.services.achievement_service import AchievementService
from app.services.certificate_service import CertificateService
from app.utils.base_controller import ValidationException, PermissionException, NotFoundException
import io
class StudentService:
    """Service for student-specific operations"""
    
    @staticmethod
    def get_dashboard(student_id: int) -> Dict[str, Any]:
        """Get student dashboard data"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise PermissionException("Only students can access dashboard")
        
        active_enrollments = Enrollment.query.filter_by(
            student_id=student_id,
            status='active'
        ).all()
        
        completed_enrollments = Enrollment.query.filter_by(
            student_id=student_id,
            status='completed'
        ).all()
        
        total_progress = 0
        if active_enrollments:
            for enrollment in active_enrollments:
                current_progress = enrollment.calculate_progress()
                if enrollment.progress_percentage != current_progress:
                    enrollment.progress_percentage = current_progress
                    
                    if current_progress >= 100:
                        enrollment.status = 'completed'
                        enrollment.completed_at = datetime.now()
            
            db.session.commit()
            
            active_enrollments = Enrollment.query.filter_by(
                student_id=student_id,
                status='active'
            ).all()
            
            completed_enrollments = Enrollment.query.filter_by(
                student_id=student_id,
                status='completed'
            ).all()
            
            if active_enrollments:
                total_progress = sum(e.progress_percentage for e in active_enrollments) / len(active_enrollments)
        
        recent_lessons = LessonProgress.query.filter_by(
            student_id=student_id
        ).order_by(desc(LessonProgress.viewed_at)).limit(5).all()
        
        recent_quiz_attempts = QuizAttempt.query.filter_by(
            student_id=student_id
        ).order_by(desc(QuizAttempt.started_at)).limit(5).all()
        
        achievements_data = AchievementService.get_student_achievements(student_id)
        
        upcoming_assignments = StudentService._get_upcoming_assignments(student_id)
        
        recent_activity = StudentService._format_recent_activity(recent_lessons, recent_quiz_attempts)
        
        all_courses = active_enrollments + completed_enrollments
        active_courses_data = []
        
        for enrollment in all_courses:
            course_data = {
                'id': enrollment.course.id,
                'title': enrollment.course.title,
                'progress': enrollment.progress_percentage,
                'teacher': enrollment.course.teacher.full_name if enrollment.course.teacher else 'Unknown',
                'enrolled_at': enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
                'status': enrollment.status,
                'completed_at': enrollment.completed_at.isoformat() if enrollment.completed_at else None
            }
            active_courses_data.append(course_data)
        
        return {
            'stats': {
                'active_courses': len(active_enrollments),
                'completed_courses': len(completed_enrollments),
                'overall_progress': round(total_progress, 1),
                'total_achievements': achievements_data['total_achievements'],
                'achievement_points': achievements_data['total_points']
            },
            'active_courses': active_courses_data, 
            'recent_activity': recent_activity,
            'upcoming_assignments': upcoming_assignments,
            'achievements': achievements_data['achievements'][:5]
        }
    
    @staticmethod
    def get_progress(student_id: int) -> Dict[str, Any]:
        """Get detailed student progress"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise PermissionException("Only students can access progress")
        
        enrollments = Enrollment.query.filter_by(student_id=student_id).all()
        progress_data = []
        
        for enrollment in enrollments:
            course = enrollment.course
            
            current_progress = enrollment.calculate_progress()
            if enrollment.progress_percentage != current_progress:
                enrollment.progress_percentage = current_progress
                
                if current_progress >= 100 and enrollment.status != 'completed':
                    enrollment.status = 'completed'
                    enrollment.completed_at = datetime.now()
            
            lesson_progress = StudentService._get_lesson_progress(student_id, course.id)
            quiz_progress = StudentService._get_quiz_progress(student_id, course)
            assignment_progress = StudentService._get_assignment_progress(student_id, course)
            
            progress_data.append({
                'course': course.to_dict(),
                'enrollment': enrollment.to_dict(),
                'lesson_progress': lesson_progress,
                'quiz_progress': quiz_progress,
                'assignment_progress': assignment_progress
            })
        
        db.session.commit()
        
        return {
            'courses': progress_data,
            'total_courses': len(progress_data)
        }
    
    @staticmethod
    def get_achievements(student_id: int) -> Dict[str, Any]:
        """Get student achievements"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise PermissionException("Only students can access achievements")
        
        earned_achievements = AchievementService.get_student_achievements(student_id)
        available_achievements = AchievementService.get_available_achievements(student_id)
        
        return {
            'earned': earned_achievements,
            'available': available_achievements
        }
    
    @staticmethod
    def get_certificates(student_id: int) -> Dict[str, Any]:
        """Get student certificates"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise PermissionException("Only students can access certificates")
        
        certificates = CertificateService.get_student_certificates(student_id)
        
        return {
            'certificates': certificates,
            'total': len(certificates)
        }
    
    @staticmethod
    def request_certificate(student_id: int, course_id: int) -> Dict[str, Any]:
        """Request certificate for completed course - FIXED LOGIC"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise PermissionException("Only students can request certificates")
        
        enrollment = Enrollment.query.filter_by(
            student_id=student_id,
            course_id=course_id
        ).first()
        
        if not enrollment:
            raise NotFoundException("You are not enrolled in this course")
        
        current_progress = enrollment.calculate_progress()
        enrollment.progress_percentage = current_progress
        
        if current_progress >= 100 and enrollment.status != 'completed':
            enrollment.status = 'completed'
            enrollment.completed_at = datetime.now()
            db.session.commit()
        
        if enrollment.status != 'completed':
            raise ValidationException(f"Course must be completed to request certificate. Current progress: {current_progress:.1f}%")
        
        existing_cert = Certificate.query.filter_by(
            student_id=student_id,
            course_id=course_id
        ).first()
        
        if existing_cert:
            return {
                'message': 'Certificate already exists',
                'certificate': existing_cert.to_dict()
            }
        
        return CertificateService.request_certificate_approval(student_id, course_id)

    
    @staticmethod
    def get_study_streak(student_id: int) -> Dict[str, Any]:
        """Get student study streak information"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise PermissionException("Only students can access study streak")
        
        lesson_progress = LessonProgress.query.filter_by(
            student_id=student_id
        ).order_by(desc(LessonProgress.viewed_at)).all()
        
        if not lesson_progress:
            return {
                'current_streak': 0,
                'longest_streak': 0,
                'last_activity': None,
                'total_study_days': 0
            }
        
        dates_with_activity = set()
        for progress in lesson_progress:
            if progress.viewed_at:
                dates_with_activity.add(progress.viewed_at.date())
        
        sorted_dates = sorted(dates_with_activity, reverse=True)
        
        current_streak = StudentService._calculate_current_streak(sorted_dates)
        longest_streak = StudentService._calculate_longest_streak(sorted_dates)
        
        return {
            'current_streak': current_streak,
            'longest_streak': longest_streak,
            'last_activity': sorted_dates[0].isoformat() if sorted_dates else None,
            'total_study_days': len(dates_with_activity)
        }
    
    @staticmethod
    def get_course_recommendations(student_id: int) -> Dict[str, Any]:
        """Get course recommendations for student"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise PermissionException("Only students can access recommendations")
        
        enrolled_courses = db.session.query(Enrollment.course_id).filter_by(
            student_id=student_id
        ).subquery()
        
        from app.models import Course
        student_categories = db.session.query(
            func.distinct(Course.category)
        ).join(enrolled_courses, Course.id == enrolled_courses.c.course_id).all()
        
        student_categories = [cat[0] for cat in student_categories if cat[0]]
        
        recommendations_query = Course.query.filter(
            Course.is_published == True,
            ~Course.id.in_(db.session.query(enrolled_courses.c.course_id))
        )
        
        if student_categories:
            recommendations_query = recommendations_query.filter(
                Course.category.in_(student_categories)
            )
        
        recommendations = recommendations_query.limit(5).all()
        
        if len(recommendations) < 5:
            popular_courses = Course.query.filter(
                Course.is_published == True,
                ~Course.id.in_(db.session.query(enrolled_courses.c.course_id)),
                ~Course.id.in_([r.id for r in recommendations])
            ).join(Enrollment).group_by(Course.id).order_by(
                desc(func.count(Enrollment.id))
            ).limit(5 - len(recommendations)).all()
            
            recommendations.extend(popular_courses)
        
        recommendations_data = []
        for course in recommendations:
            course_data = course.to_dict()
            course_data['recommendation_reason'] = (
                f"Based on your interest in {course.category}" 
                if course.category in student_categories 
                else "Popular course"
            )
            recommendations_data.append(course_data)
        
        return {
            'recommendations': recommendations_data,
            'total': len(recommendations_data)
        }
    
    @staticmethod
    def _get_upcoming_assignments(student_id: int) -> List[Dict[str, Any]]:
        """Get upcoming assignments for student"""
        week_from_now = datetime.now() + timedelta(days=7)
        
        upcoming_assignments = Assignment.query.join(
            Enrollment, Assignment.course_id == Enrollment.course_id
        ).filter(
            Enrollment.student_id == student_id,
            Enrollment.status.in_(['active', 'completed']),  
            Assignment.due_date <= week_from_now,
            Assignment.due_date >= datetime.now()
        ).order_by(Assignment.due_date).all()
        
        return [
            {
                'id': a.id,
                'title': a.title,
                'course': a.course.title,
                'due_date': a.due_date.isoformat() if a.due_date else None,
                'days_remaining': (a.due_date - datetime.now()).days if a.due_date else 0
            }
            for a in upcoming_assignments
        ]
    
    @staticmethod
    def _format_recent_activity(recent_lessons: List, recent_quiz_attempts: List) -> List[Dict[str, Any]]:
        """Format recent activity for dashboard"""
        recent_activity = []
        
        for lesson in recent_lessons:
            recent_activity.append({
                'type': 'lesson',
                'title': f"Viewed: {lesson.lesson.title}",
                'course': lesson.lesson.course.title,
                'timestamp': lesson.viewed_at.isoformat() if lesson.viewed_at else None
            })
        
        for attempt in recent_quiz_attempts:
            recent_activity.append({
                'type': 'quiz',
                'title': f"Quiz: {attempt.quiz.title}",
                'course': attempt.quiz.course.title,
                'score': attempt.score,
                'timestamp': attempt.started_at.isoformat() if attempt.started_at else None
            })
        
        recent_activity.sort(key=lambda x: x['timestamp'] or '', reverse=True)
        return recent_activity[:10]
    
    @staticmethod
    def _get_lesson_progress(student_id: int, course_id: int) -> Dict[str, Any]:
        """Get lesson progress for a course"""
        from app.models import Course, Lesson
        course = Course.query.get(course_id)
        total_lessons = course.lessons.count()
        
        completed_lessons = LessonProgress.query.filter_by(
            student_id=student_id
        ).join(Lesson).filter(
            Lesson.course_id == course_id,
            LessonProgress.completed_at.isnot(None)
        ).count()
        
        return {
            'completed': completed_lessons,
            'total': total_lessons,
            'percentage': (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0
        }
    
    @staticmethod
    def _get_quiz_progress(student_id: int, course) -> List[Dict[str, Any]]:
        """Get quiz progress for a course"""
        quiz_progress = []
        
        for quiz in course.quizzes.all():
            best_attempt = QuizAttempt.query.filter_by(
                student_id=student_id,
                quiz_id=quiz.id,
                status='completed'
            ).order_by(QuizAttempt.score.desc()).first()
            
            quiz_progress.append({
                'quiz_id': quiz.id,
                'quiz_title': quiz.title,
                'best_score': best_attempt.score if best_attempt else None,
                'passed': best_attempt.score >= quiz.passing_score if best_attempt else False,
                'attempts': QuizAttempt.query.filter_by(
                    student_id=student_id, quiz_id=quiz.id
                ).count()
            })
        
        return quiz_progress
    
    @staticmethod
    def _get_assignment_progress(student_id: int, course) -> List[Dict[str, Any]]:
        """Get assignment progress for a course"""
        assignment_progress = []
        
        for assignment in course.assignments.all():
            submission = AssignmentSubmission.query.filter_by(
                student_id=student_id,
                assignment_id=assignment.id
            ).first()
            
            assignment_progress.append({
                'assignment_id': assignment.id,
                'assignment_title': assignment.title,
                'submitted': submission is not None,
                'grade': submission.grade if submission else None,
                'status': submission.status if submission else 'not_submitted'
            })
        
        return assignment_progress
    
    @staticmethod
    def _calculate_current_streak(sorted_dates: List) -> int:
        """Calculate current study streak"""
        if not sorted_dates:
            return 0
        
        today = datetime.now().date()
        current_streak = 0
        
        if sorted_dates[0] == today or sorted_dates[0] == today - timedelta(days=1):
            current_streak = 1
            last_date = sorted_dates[0]
            
            for i in range(1, len(sorted_dates)):
                if (last_date - sorted_dates[i]).days == 1:
                    current_streak += 1
                    last_date = sorted_dates[i]
                else:
                    break
        
        return current_streak
    
    @staticmethod
    def _calculate_longest_streak(sorted_dates: List) -> int:
        """Calculate longest study streak"""
        if not sorted_dates:
            return 0
        
        longest_streak = 1
        temp_streak = 1
        
        for i in range(1, len(sorted_dates)):
            if (sorted_dates[i-1] - sorted_dates[i]).days == 1:
                temp_streak += 1
            else:
                longest_streak = max(longest_streak, temp_streak)
                temp_streak = 1
        
        return max(longest_streak, temp_streak)
    
    @staticmethod
    def generate_certificate_pdf(certificate) -> io.BytesIO:
        """Generate a PDF certificate"""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.enums import TA_CENTER
            
        except ImportError:
            return StudentService._generate_simple_pdf(certificate)
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.5*inch, leftMargin=0.5*inch, topMargin=0.5*inch, bottomMargin=0.5*inch)
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=28, spaceAfter=30, alignment=TA_CENTER, textColor=colors.HexColor('#1f2937'), fontName='Helvetica-Bold')
        
        story = []
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph("🏆", title_style))
        story.append(Paragraph("CERTIFICATE OF COMPLETION", title_style))
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph(certificate.student.full_name, title_style))
        story.append(Paragraph(certificate.course.title, title_style))
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph(f"Issued: {certificate.issued_at.strftime('%B %d, %Y')}", styles['Normal']))
        story.append(Paragraph(f"Certificate ID: {certificate.certificate_code}", styles['Normal']))
        
        doc.build(story)
        buffer.seek(0)
        return buffer

    @staticmethod
    def _generate_simple_pdf(certificate) -> io.BytesIO:
        """Fallback PDF generation without reportlab"""
        from fpdf import FPDF
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font('Arial', 'B', 24)
        pdf.cell(0, 20, 'CERTIFICATE OF COMPLETION', 0, 1, 'C')
        pdf.ln(20)
        pdf.set_font('Arial', 'B', 18)
        pdf.cell(0, 15, certificate.student.full_name, 0, 1, 'C')
        pdf.ln(10)
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 15, certificate.course.title, 0, 1, 'C')
        pdf.ln(20)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 8, f'Issue Date: {certificate.issued_at.strftime("%B %d, %Y")}', 0, 1, 'C')
        pdf.cell(0, 8, f'Certificate ID: {certificate.certificate_code}', 0, 1, 'C')
        
        buffer = io.BytesIO()
        pdf_content = pdf.output(dest='S').encode('latin1')
        buffer.write(pdf_content)
        buffer.seek(0)
        return buffer
    
    @staticmethod
    def get_dashboard(student_id: int) -> Dict[str, Any]:
        """Get student dashboard data"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise PermissionException("Only students can access dashboard")
        
        active_enrollments = Enrollment.query.filter_by(
            student_id=student_id,
            status='active'
        ).all()
        
        completed_enrollments = Enrollment.query.filter_by(
            student_id=student_id,
            status='completed'
        ).all()
        
        total_progress = 0
        if active_enrollments:
            for enrollment in active_enrollments:
                current_progress = enrollment.calculate_progress()
                if enrollment.progress_percentage != current_progress:
                    enrollment.progress_percentage = current_progress
                    
                    if current_progress >= 100:
                        enrollment.status = 'completed'
                        enrollment.completed_at = datetime.now()
            
            db.session.commit()
            
            active_enrollments = Enrollment.query.filter_by(
                student_id=student_id,
                status='active'
            ).all()
            
            completed_enrollments = Enrollment.query.filter_by(
                student_id=student_id,
                status='completed'
            ).all()
            
            if active_enrollments:
                total_progress = sum(e.progress_percentage for e in active_enrollments) / len(active_enrollments)
        
        recent_lessons = LessonProgress.query.filter_by(
            student_id=student_id
        ).order_by(desc(LessonProgress.viewed_at)).limit(5).all()
        
        recent_quiz_attempts = QuizAttempt.query.filter_by(
            student_id=student_id
        ).order_by(desc(QuizAttempt.started_at)).limit(5).all()
        
        achievements_data = AchievementService.get_student_achievements(student_id)
        
        upcoming_assignments = StudentService._get_upcoming_assignments(student_id)
        
        recent_activity = StudentService._format_recent_activity(recent_lessons, recent_quiz_attempts)
        
        all_courses = active_enrollments + completed_enrollments
        active_courses_data = []
        
        for enrollment in all_courses:
            course_data = {
                'id': enrollment.course.id,
                'title': enrollment.course.title,
                'progress': enrollment.progress_percentage,
                'teacher': enrollment.course.teacher.full_name if enrollment.course.teacher else 'Unknown',
                'enrolled_at': enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
                'status': enrollment.status,
                'completed_at': enrollment.completed_at.isoformat() if enrollment.completed_at else None
            }
            active_courses_data.append(course_data)
        
        return {
            'stats': {
                'active_courses': len(active_enrollments),
                'completed_courses': len(completed_enrollments),
                'overall_progress': round(total_progress, 1),
                'total_achievements': achievements_data['total_achievements'],
                'achievement_points': achievements_data['total_points']
            },
            'active_courses': active_courses_data, 
            'recent_activity': recent_activity,
            'upcoming_assignments': upcoming_assignments,
            'achievements': achievements_data['achievements'][:5]
        }