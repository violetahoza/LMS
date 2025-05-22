from datetime import datetime
from app.models import db, Certificate, Enrollment, Course, User
from app.utils.helpers import generate_certificate_code

class CertificateService:
    """Service class for certificate generation and management"""
    
    @staticmethod
    def check_course_completion(student_id, course_id):
        """Check if student has completed all course requirements"""
        enrollment = Enrollment.query.filter_by(
            student_id=student_id,
            course_id=course_id
        ).first()
        
        if not enrollment:
            return False, "Not enrolled in this course"
        
        if enrollment.status != 'completed':
            return False, "Course not completed"
        
        course = Course.query.get(course_id)
        
        # Check if all lessons are completed
        from app.models import Lesson, LessonProgress
        total_lessons = course.lessons.count()
        completed_lessons = LessonProgress.query.filter_by(
            student_id=student_id
        ).join(Lesson).filter(
            Lesson.course_id == course_id,
            LessonProgress.completed_at.isnot(None)
        ).count()
        
        if completed_lessons < total_lessons:
            return False, f"Only {completed_lessons}/{total_lessons} lessons completed"
        
        # Check if all required quizzes are passed
        from app.models import Quiz, QuizAttempt
        required_quizzes = course.quizzes.all()
        
        for quiz in required_quizzes:
            best_attempt = QuizAttempt.query.filter_by(
                student_id=student_id,
                quiz_id=quiz.id,
                status='completed'
            ).order_by(QuizAttempt.score.desc()).first()
            
            if not best_attempt or best_attempt.score < quiz.passing_score:
                return False, f"Quiz '{quiz.title}' not passed"
        
        # Check if all assignments are submitted
        from app.models import Assignment, AssignmentSubmission
        required_assignments = course.assignments.all()
        
        for assignment in required_assignments:
            submission = AssignmentSubmission.query.filter_by(
                student_id=student_id,
                assignment_id=assignment.id
            ).first()
            
            if not submission:
                return False, f"Assignment '{assignment.title}' not submitted"
        
        return True, "All requirements completed"
    
    @staticmethod
    def generate_certificate(student_id, course_id):
        """Generate a certificate for course completion"""
        # Check if certificate already exists
        existing_cert = Certificate.query.filter_by(
            student_id=student_id,
            course_id=course_id
        ).first()
        
        if existing_cert:
            return existing_cert
        
        # Verify completion
        is_complete, message = CertificateService.check_course_completion(student_id, course_id)
        if not is_complete:
            raise ValueError(message)
        
        # Generate certificate
        certificate = Certificate(
            student_id=student_id,
            course_id=course_id,
            certificate_code=generate_certificate_code()
        )
        
        db.session.add(certificate)
        db.session.commit()
        
        return certificate
    
    @staticmethod
    def verify_certificate(certificate_code):
        """Verify a certificate by its code"""
        certificate = Certificate.query.filter_by(
            certificate_code=certificate_code
        ).first()
        
        if not certificate:
            return None
        
        return {
            'valid': True,
            'student_name': certificate.student.full_name,
            'course_title': certificate.course.title,
            'issued_date': certificate.issued_at,
            'certificate_code': certificate_code
        }
    
    @staticmethod
    def get_student_certificates(student_id):
        """Get all certificates earned by a student"""
        certificates = Certificate.query.filter_by(
            student_id=student_id
        ).order_by(Certificate.issued_at.desc()).all()
        
        return [cert.to_dict() for cert in certificates]
    
    @staticmethod
    def get_course_certificates(course_id):
        """Get all certificates issued for a course"""
        certificates = Certificate.query.filter_by(
            course_id=course_id
        ).order_by(Certificate.issued_at.desc()).all()
        
        cert_data = []
        for cert in certificates:
            data = cert.to_dict()
            data['student'] = cert.student.to_dict()
            cert_data.append(data)
        
        return cert_data
    
    @staticmethod
    def generate_bulk_certificates(course_id):
        """Generate certificates for all eligible students in a course"""
        course = Course.query.get(course_id)
        if not course:
            raise ValueError("Course not found")
        
        # Get all completed enrollments
        completed_enrollments = Enrollment.query.filter_by(
            course_id=course_id,
            status='completed'
        ).all()
        
        generated = []
        errors = []
        
        for enrollment in completed_enrollments:
            try:
                cert = CertificateService.generate_certificate(
                    enrollment.student_id,
                    course_id
                )
                generated.append(cert)
            except Exception as e:
                errors.append({
                    'student_id': enrollment.student_id,
                    'student_name': enrollment.student.full_name,
                    'error': str(e)
                })
        
        return {
            'generated': len(generated),
            'errors': errors,
            'certificates': [cert.to_dict() for cert in generated]
        }