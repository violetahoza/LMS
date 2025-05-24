from datetime import datetime
from typing import Dict, Any, List
from app.models import db, User, Course, Certificate, Enrollment
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
        """Generate a certificate for a completed course"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise PermissionException("Only students can generate certificates")
        
        course = Course.query.get(course_id)
        if not course:
            raise NotFoundException("Course not found")
        
        # Check if student completed the course
        enrollment = Enrollment.query.filter_by(
            student_id=student_id,
            course_id=course_id,
            status='completed'
        ).first()
        
        if not enrollment:
            raise ValidationException("Course must be completed to generate certificate")
        
        # Check if certificate already exists
        existing_cert = Certificate.query.filter_by(
            student_id=student_id,
            course_id=course_id
        ).first()
        
        if existing_cert:
            return existing_cert
        
        # Generate new certificate
        certificate_code = generate_certificate_code()
        
        certificate = Certificate(
            student_id=student_id,
            course_id=course_id,
            certificate_code=certificate_code
        )
        
        db.session.add(certificate)
        db.session.commit()
        
        return certificate
    
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
            'verified_at': datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def get_certificate_details(certificate_id: int) -> Dict[str, Any]:
        """Get detailed certificate information"""
        certificate = Certificate.query.get(certificate_id)
        if not certificate:
            raise NotFoundException("Certificate not found")
        
        return certificate.to_dict()