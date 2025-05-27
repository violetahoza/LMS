from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.notification_service import NotificationService
from app.utils.base_controller import BaseController

bp = Blueprint('notifications', __name__, url_prefix='/api/notifications')

@bp.route('/', methods=['GET'])
@jwt_required()
def get_notifications():
    """Get notifications for current user"""
    user_id = int(get_jwt_identity())
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    
    return BaseController.handle_list_request(
        NotificationService.get_user_notifications,
        user_id,
        page=page,
        per_page=per_page,
        unread_only=unread_only
    )

@bp.route('/<int:notification_id>/read', methods=['POST'])
@jwt_required()
def mark_as_read(notification_id):
    """Mark a notification as read"""
    user_id = int(get_jwt_identity())
    
    return BaseController.handle_request(
        NotificationService.mark_as_read,
        user_id,
        notification_id,
        success_message="Notification marked as read"
    )

@bp.route('/mark-all-read', methods=['POST'])
@jwt_required()
def mark_all_as_read():
    """Mark all notifications as read"""
    user_id = int(get_jwt_identity())
    
    return BaseController.handle_request(
        NotificationService.mark_all_as_read,
        user_id,
        success_message="All notifications marked as read"
    )

@bp.route('/<int:notification_id>', methods=['DELETE'])
@jwt_required()
def delete_notification(notification_id):
    """Delete a notification"""
    user_id = int(get_jwt_identity())
    
    return BaseController.handle_request(
        NotificationService.delete_notification,
        user_id,
        notification_id,
        success_message="Notification deleted"
    )

@bp.route('/unread-count', methods=['GET'])
@jwt_required()
def get_unread_count():
    """Get count of unread notifications"""
    user_id = int(get_jwt_identity())
    
    data = NotificationService.get_user_notifications(user_id, per_page=1)
    return jsonify({
        'unread_count': data['unread_count']
    })

@bp.route('/bulk-delete', methods=['POST'])
@jwt_required()
def bulk_delete_notifications():
    """Delete multiple notifications"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    notification_ids = data.get('notification_ids', [])
    
    if not notification_ids:
        return jsonify({'error': 'No notification IDs provided'}), 400
    
    return BaseController.handle_request(
        NotificationService.bulk_delete_notifications,
        user_id,
        notification_ids,
        success_message=f"{len(notification_ids)} notifications deleted"
    )

@bp.route('/preferences', methods=['PUT'])
@jwt_required()
def update_notification_preferences():
    """Update user notification preferences"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    return BaseController.handle_request(
        NotificationService.update_notification_preferences,
        user_id,
        data,
        success_message="Notification preferences updated"
    )