from datetime import datetime, timedelta
from typing import Dict, Any, List
from app.models import db, User, Course, Certificate, Enrollment, CertificateRequest
from app.utils.base_controller import ValidationException, PermissionException, NotFoundException
from app.utils.helpers import generate_certificate_code

class CertificateService:
    """Service for certificate-related operations"""
    
    @staticmethod
    def get_student_certificates(student_id: int) -> List[Dict[str, Any]]:
        """Get all certificates for a student"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise PermissionException("Only students can access certificates")
        
        certificates = Certificate.query.filter_by(student_id=student_id).all()
        
        certificates_data = []
        for cert in certificates:
            cert_data = cert.to_dict()
            certificates_data.append(cert_data)
        
        return certificates_data
    
    @staticmethod
    def generate_certificate(student_id: int, course_id: int) -> Certificate:
        """Generate a certificate directly for a student (used by student service)"""
        student = User.query.get(student_id)
        if not student or not student.is_student():
            raise ValidationException("Invalid student")
        
        course = Course.query.get(course_id)
        if not course:
            raise NotFoundException("Course not found")
        
        enrollment = Enrollment.query.filter_by(
            student_id=student_id,
            course_id=course_id
        ).first()
        
        if not enrollment:
            raise ValidationException("Student is not enrolled in this course")
        
        current_progress = enrollment.calculate_progress()
        enrollment.progress_percentage = current_progress
        
        if current_progress >= 100 and enrollment.status != 'completed':
            enrollment.status = 'completed'
            enrollment.completed_at = datetime.now()
        
        if enrollment.status != 'completed':
            raise ValidationException("Student has not completed this course")
        
        existing_cert = Certificate.query.filter_by(
            student_id=student_id,
            course_id=course_id
        ).first()
        
        if existing_cert:
            return existing_cert
        
        certificate_code = generate_certificate_code()
        
        certificate = Certificate(
            student_id=student_id,
            course_id=course_id,
            certificate_code=certificate_code
        )
        
        db.session.add(certificate)
        db.session.commit()
        
        return certificate.to_dict()
    
    @staticmethod
    def get_pending_certificates(admin_id: int) -> Dict[str, Any]:
        """Get students eligible for certificates (admin only)"""
        user = User.query.get(admin_id)
        if not user or not user.is_admin():
            raise PermissionException("Only admins can access pending certificates")
        
        completed_enrollments = db.session.query(Enrollment).filter(
            Enrollment.status == 'completed',
            ~Enrollment.student_id.in_(
                db.session.query(Certificate.student_id).filter(
                    Certificate.course_id == Enrollment.course_id
                )
            )
        ).all()
        
        pending_certs = []
        for enrollment in completed_enrollments:
            existing_request = CertificateRequest.query.filter_by(
                student_id=enrollment.student_id,
                course_id=enrollment.course_id,
                status='pending'
            ).first()
            
            pending_certs.append({
                'student_id': enrollment.student_id,
                'student_name': enrollment.student.full_name,
                'student_email': enrollment.student.email,
                'course_id': enrollment.course_id,
                'course_title': enrollment.course.title,
                'completed_at': enrollment.completed_at.isoformat() if enrollment.completed_at else None,
                'teacher_name': enrollment.course.teacher.full_name if enrollment.course.teacher else None,
                'has_pending_request': existing_request is not None,
                'progress_percentage': enrollment.progress_percentage
            })
        
        return {
            'pending_certificates': pending_certs,
            'total': len(pending_certs)
        }
    
    @staticmethod
    def issue_certificate(admin_id: int, student_id: int, course_id: int) -> Dict[str, Any]:
        """Issue a certificate (admin only)"""
        user = User.query.get(admin_id)
        if not user or not user.is_admin():
            raise PermissionException("Only admins can issue certificates")
        
        student = User.query.get(student_id)
        if not student or not student.is_student():
            raise ValidationException("Invalid student")
        
        course = Course.query.get(course_id)
        if not course:
            raise NotFoundException("Course not found")
        
        enrollment = Enrollment.query.filter_by(
            student_id=student_id,
            course_id=course_id,
            status='completed'
        ).first()
        
        if not enrollment:
            raise ValidationException("Student has not completed this course")
        
        existing_cert = Certificate.query.filter_by(
            student_id=student_id,
            course_id=course_id
        ).first()
        
        if existing_cert:
            raise ValidationException("Certificate already exists for this student and course")
        
        certificate_code = generate_certificate_code()
        
        certificate = Certificate(
            student_id=student_id,
            course_id=course_id,
            certificate_code=certificate_code
        )
        
        db.session.add(certificate)
        
        pending_request = CertificateRequest.query.filter_by(
            student_id=student_id,
            course_id=course_id,
            status='pending'
        ).first()
        
        if pending_request:
            pending_request.status = 'approved'
            pending_request.reviewed_by = admin_id
            pending_request.reviewed_at = datetime.now()
        
        db.session.commit()
        
        try:
            from app.services.notification_service import NotificationService
            NotificationService.notify_certificate_issued(
                student_id=student_id,
                course_id=course_id,
                certificate_code=certificate_code
            )
        except Exception as e:
            print(f"Failed to send certificate notification: {e}")
        
        return {
            'message': 'Certificate issued successfully',
            'certificate': certificate.to_dict() 
        }

    @staticmethod
    def bulk_issue_certificates(admin_id: int, certificate_requests: List[Dict[str, int]]) -> Dict[str, Any]:
        """Issue multiple certificates at once (admin only)"""
        user = User.query.get(admin_id)
        if not user or not user.is_admin():
            raise PermissionException("Only admins can issue certificates")
        
        issued_certificates = []
        errors = []
        
        for request in certificate_requests:
            try:
                certificate = CertificateService.issue_certificate(
                    admin_id=admin_id,
                    student_id=request['student_id'],
                    course_id=request['course_id']
                )
                issued_certificates.append(certificate.to_dict())
            except Exception as e:
                errors.append({
                    'student_id': request['student_id'],
                    'course_id': request['course_id'],
                    'error': str(e)
                })
        
        return {
            'issued_certificates': issued_certificates,
            'errors': errors,
            'total_issued': len(issued_certificates),
            'total_errors': len(errors)
        }
    
    @staticmethod
    def revoke_certificate(admin_id: int, certificate_id: int) -> Dict[str, str]:
        """Revoke a certificate (admin only)"""
        user = User.query.get(admin_id)
        if not user or not user.is_admin():
            raise PermissionException("Only admins can revoke certificates")
        
        certificate = Certificate.query.get(certificate_id)
        if not certificate:
            raise NotFoundException("Certificate not found")
        
        db.session.delete(certificate)
        db.session.commit()
        
        return {'message': 'Certificate revoked successfully'}
    
    @staticmethod
    def verify_certificate(certificate_code: str) -> Dict[str, Any]:
        """Verify a certificate by its code"""
        certificate = Certificate.query.filter_by(
            certificate_code=certificate_code
        ).first()
        
        if not certificate:
            raise NotFoundException("Certificate not found")
        
        return {
            'certificate': certificate.to_dict(),
            'valid': True,
            'verified_at': datetime.now().isoformat()
        }
    
    @staticmethod
    def get_certificate_details(certificate_id: int) -> Dict[str, Any]:
        """Get detailed certificate information"""
        certificate = Certificate.query.get(certificate_id)
        if not certificate:
            raise NotFoundException("Certificate not found")
        
        return certificate.to_dict()
    
    @staticmethod
    def request_certificate_approval(student_id: int, course_id: int) -> Dict[str, Any]:
        """Request certificate for completed course - FIXED DUPLICATE HANDLING"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise PermissionException("Only students can request certificates")
        
        course = Course.query.get(course_id)
        if not course:
            raise NotFoundException("Course not found")
        
        enrollment = Enrollment.query.filter_by(
            student_id=student_id,
            course_id=course_id,
            status='completed'
        ).first()
        
        if not enrollment:
            raise ValidationException("Course must be completed to request certificate")
        
        existing_cert = Certificate.query.filter_by(
            student_id=student_id,
            course_id=course_id
        ).first()
        
        if existing_cert:
            return {
                'message': 'Certificate already exists for this course',
                'certificate': existing_cert.to_dict()
            }
        
        existing_request = CertificateRequest.query.filter_by(
            student_id=student_id,
            course_id=course_id
        ).first()
        
        if existing_request:
            if existing_request.status == 'pending':
                return {
                    'message': 'Certificate request already submitted and is pending admin review',
                    'request': existing_request.to_dict()
                }
            elif existing_request.status == 'approved':
                return {
                    'message': 'Certificate request has already been approved',
                    'request': existing_request.to_dict()
                }
            elif existing_request.status == 'rejected':
                existing_request.status = 'pending'
                existing_request.requested_at = datetime.now()
                existing_request.reviewed_by = None
                existing_request.reviewed_at = None
                existing_request.rejection_reason = None
                db.session.commit()
                
                return {
                    'message': 'Certificate request resubmitted successfully',
                    'request': existing_request.to_dict()
                }
        
        try:
            cert_request = CertificateRequest(
                student_id=student_id,
                course_id=course_id,
                requested_at=datetime.now(),
                status='pending'
            )
            
            db.session.add(cert_request)
            db.session.commit()
            
            return {
                'message': 'Certificate request submitted successfully',
                'request': cert_request.to_dict()
            }
        except Exception as e:
            db.session.rollback()
            existing_request = CertificateRequest.query.filter_by(
                student_id=student_id,
                course_id=course_id
            ).first()
            
            if existing_request:
                return {
                    'message': 'Certificate request already submitted and is pending admin review',
                    'request': existing_request.to_dict()
                }
            else:
                raise e
    
    @staticmethod
    def get_certificate_requests(admin_id: int) -> Dict[str, Any]:
        """Get all certificate requests (admin only)"""
        user = User.query.get(admin_id)
        if not user or not user.is_admin():
            raise PermissionException("Only admins can access certificate requests")
        
        pending_requests = CertificateRequest.query.filter_by(status='pending').all()
        
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_reviewed = CertificateRequest.query.filter(
            CertificateRequest.status.in_(['approved', 'rejected']),
            CertificateRequest.reviewed_at >= thirty_days_ago
        ).order_by(CertificateRequest.reviewed_at.desc()).all()
        
        recent_approved_count = len([r for r in recent_reviewed if r.status == 'approved'])
        recent_rejected_count = len([r for r in recent_reviewed if r.status == 'rejected'])
    
        return {
            'pending_requests': [req.to_dict() for req in pending_requests],
            'recent_reviewed': [req.to_dict() for req in recent_reviewed],
            'total_pending': len(pending_requests),
            'total_recent_reviewed': len(recent_reviewed),
            'recent_approved_count': recent_approved_count,
            'recent_rejected_count': recent_rejected_count,
            'stats': {
                'pending': len(pending_requests),
                'recent_approved': recent_approved_count,
                'recent_rejected': recent_rejected_count,
                'total_recent': len(recent_reviewed)
            }
        }
    
    @staticmethod
    def approve_certificate_request(admin_id: int, request_id: int) -> Dict[str, Any]:
        """Approve a certificate request (admin only)"""
        user = User.query.get(admin_id)
        if not user or not user.is_admin():
            raise PermissionException("Only admins can approve certificate requests")
        
        cert_request = CertificateRequest.query.get(request_id)
        if not cert_request:
            raise NotFoundException("Certificate request not found")
        
        if cert_request.status != 'pending':
            raise ValidationException("Only pending requests can be approved")
        
        certificate = CertificateService.issue_certificate(
            admin_id=admin_id,
            student_id=cert_request.student_id,
            course_id=cert_request.course_id
        )
        
        try:
            from app.services.notification_service import NotificationService
            NotificationService.notify_certificate_request_approved(
                student_id=cert_request.student_id,
                course_id=cert_request.course_id,
                certificate_code=certificate.certificate_code
            )
        except Exception as e:
            print(f"Error sending certificate approval notification: {e}")
        
        return {
            'message': 'Certificate request approved and issued',
            'certificate': certificate,
            'request': cert_request.to_dict()
        }

    @staticmethod
    def reject_certificate_request(admin_id: int, request_id: int, reason: str) -> Dict[str, Any]:
        """Reject a certificate request (admin only)"""
        user = User.query.get(admin_id)
        if not user or not user.is_admin():
            raise PermissionException("Only admins can reject certificate requests")
        
        cert_request = CertificateRequest.query.get(request_id)
        if not cert_request:
            raise NotFoundException("Certificate request not found")
        
        if cert_request.status != 'pending':
            raise ValidationException("Only pending requests can be rejected")
        
        cert_request.status = 'rejected'
        cert_request.reviewed_by = admin_id
        cert_request.reviewed_at = datetime.now()
        cert_request.rejection_reason = reason
        
        db.session.commit()
        
        try:
            from app.services.notification_service import NotificationService
            NotificationService.notify_certificate_request_rejected(
                student_id=cert_request.student_id,
                course_id=cert_request.course_id,
                reason=reason
            )
        except Exception as e:
            print(f"Error sending certificate rejection notification: {e}")
        
        return {
            'message': 'Certificate request rejected',
            'request': cert_request.to_dict()
        }
    