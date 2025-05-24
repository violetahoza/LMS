from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.auth_service import AuthService
from app.utils.base_controller import BaseController

bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        result = AuthService.register_user(data)
        return jsonify({
            'message': result['message'],
            'data': result
        }), 201
        
    except Exception as e:
        error_message = str(e)
        if "Registration failed:" in error_message:
            error_message = error_message.replace("Registration failed: ", "")
        
        return jsonify({'error': error_message}), 400

@bp.route('/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        result = AuthService.login_user(data)
        return jsonify({
            'message': result['message'],
            'data': result
        }), 200
        
    except Exception as e:
        error_message = str(e)
        if "Login failed:" in error_message:
            error_message = error_message.replace("Login failed: ", "")
        
        return jsonify({'error': error_message}), 401

@bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user profile"""
    try:
        user_id = int(get_jwt_identity())
        result = AuthService.get_user_profile(user_id)
        return jsonify({
            'message': 'Profile retrieved successfully',
            'data': result
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update current user profile"""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        result = AuthService.update_user_profile(user_id, data)
        return jsonify({
            'message': result['message'],
            'data': result
        }), 200
        
    except Exception as e:
        error_message = str(e)
        if "Failed to update profile:" in error_message:
            error_message = error_message.replace("Failed to update profile: ", "")
        
        return jsonify({'error': error_message}), 400

@bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change user password"""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        result = AuthService.change_password(user_id, data)
        return jsonify(result), 200
        
    except Exception as e:
        error_message = str(e)
        if "Failed to change password:" in error_message:
            error_message = error_message.replace("Failed to change password: ", "")
        
        return jsonify({'error': error_message}), 400