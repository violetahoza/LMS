from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.certificate_service import CertificateService
from app.utils.base_controller import BaseController
from app.utils.decorators import admin_required, student_required

bp = Blueprint('certificates', __name__, url_prefix='/api/certificates')

@bp.route('/pending', methods=['GET'])
@admin_required()
def get_pending_certificates():
    """Get students eligible for certificates (admin only)"""
    admin_id = int(get_jwt_identity())
    
    return BaseController.handle_request(
        CertificateService.get_pending_certificates,
        admin_id
    )

@bp.route('/issue', methods=['POST'])
@admin_required()
def issue_certificate():
    """Issue a certificate (admin only)"""
    admin_id = int(get_jwt_identity())
    data = request.get_json()
    
    return BaseController.handle_request(
        CertificateService.issue_certificate,
        admin_id,
        data['student_id'],
        data['course_id'],
        success_message="Certificate issued successfully",
        success_code=201
    )

@bp.route('/bulk-issue', methods=['POST'])
@admin_required()
def bulk_issue_certificates():
    """Issue multiple certificates at once (admin only)"""
    admin_id = int(get_jwt_identity())
    data = request.get_json()
    
    return BaseController.handle_request(
        CertificateService.bulk_issue_certificates,
        admin_id,
        data['certificate_requests'],
        success_message="Certificates processed successfully"
    )

@bp.route('/<int:certificate_id>/revoke', methods=['DELETE'])
@admin_required()
def revoke_certificate(certificate_id):
    """Revoke a certificate (admin only)"""
    admin_id = int(get_jwt_identity())
    
    return BaseController.handle_request(
        CertificateService.revoke_certificate,
        admin_id,
        certificate_id,
        success_message="Certificate revoked successfully"
    )

@bp.route('/verify/<string:certificate_code>', methods=['GET'])
def verify_certificate(certificate_code):
    """Verify a certificate by its code (public endpoint)"""
    return BaseController.handle_request(
        CertificateService.verify_certificate,
        certificate_code
    )

@bp.route('/request/<int:course_id>', methods=['POST'])
@student_required()
def request_certificate(course_id):
    """Student requests certificate approval"""
    student_id = int(get_jwt_identity())
    
    return BaseController.handle_request(
        CertificateService.request_certificate_approval,
        student_id,
        course_id,
        success_message="Certificate request submitted",
        success_code=201
    )

@bp.route('/requests', methods=['GET'])
@admin_required()
def get_certificate_requests():
    """Get all certificate requests (admin only)"""
    admin_id = int(get_jwt_identity())
    
    return BaseController.handle_request(
        CertificateService.get_certificate_requests,
        admin_id
    )

@bp.route('/requests/<int:request_id>/approve', methods=['POST'])
@admin_required()
def approve_certificate_request(request_id):
    """Approve a certificate request (admin only)"""
    admin_id = int(get_jwt_identity())
    
    return BaseController.handle_request(
        CertificateService.approve_certificate_request,
        admin_id,
        request_id,
        success_message="Certificate request approved and issued"
    )

@bp.route('/requests/<int:request_id>/reject', methods=['POST'])
@admin_required()
def reject_certificate_request(request_id):
    """Reject a certificate request (admin only)"""
    admin_id = int(get_jwt_identity())
    data = request.get_json()
    reason = data.get('reason', 'Request rejected by administrator')
    
    return BaseController.handle_request(
        CertificateService.reject_certificate_request,
        admin_id,
        request_id,
        reason,
        success_message="Certificate request rejected"
    )