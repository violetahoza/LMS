from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.messaging_service import MessagingService
from app.utils.base_controller import BaseController

bp = Blueprint('messages', __name__, url_prefix='/api/messages')

@bp.route('/send', methods=['POST'])
@jwt_required()
def send_message():
    """Send a message"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    return BaseController.handle_request(
        MessagingService.send_message,
        user_id,
        data,
        success_message="Message sent successfully",
        success_code=201
    )

@bp.route('/', methods=['GET'])
@jwt_required()
def get_messages():
    """Get messages for current user"""
    user_id = int(get_jwt_identity())
    message_type = request.args.get('type', 'received')  # received, sent, all
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    return BaseController.handle_list_request(
        MessagingService.get_messages,
        user_id,
        message_type=message_type,
        page=page,
        per_page=per_page
    )

@bp.route('/<int:message_id>', methods=['GET'])
@jwt_required()
def get_message(message_id):
    """Get a specific message"""
    user_id = int(get_jwt_identity())
    
    return BaseController.handle_request(
        MessagingService.get_message,
        user_id,
        message_id
    )

@bp.route('/<int:message_id>/read', methods=['POST'])
@jwt_required()
def mark_as_read(message_id):
    """Mark a message as read"""
    user_id = int(get_jwt_identity())
    
    return BaseController.handle_request(
        MessagingService.mark_as_read,
        user_id,
        message_id,
        success_message="Message marked as read"
    )

@bp.route('/conversations', methods=['GET'])
@jwt_required()
def get_conversations():
    """Get conversations for current user"""
    user_id = int(get_jwt_identity())
    
    return BaseController.handle_request(
        MessagingService.get_conversations,
        user_id
    )

@bp.route('/conversations/<int:partner_id>', methods=['GET'])
@jwt_required()
def get_conversation_messages(partner_id):
    """Get messages in a conversation with a specific user"""
    user_id = int(get_jwt_identity())
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    return BaseController.handle_list_request(
        MessagingService.get_conversation_messages,
        user_id,
        partner_id,
        page=page,
        per_page=per_page
    )