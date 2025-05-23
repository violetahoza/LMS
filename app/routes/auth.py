# app/routes/auth.py
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_login import login_user, logout_user
from werkzeug.exceptions import BadRequest

from app.services.auth_service import AuthService
from app.utils.base_controller import BaseController

bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@bp.route('/register', methods=['POST'])
def register():
    """Register a new user - API endpoint"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        result = AuthService.register_user(data)
        return jsonify({
            'message': 'User registered successfully',
            'data': result
        }), 201
        
    except ValueError as e:
        # Handle validation errors
        error_msg = str(e)
        field_errors = {}
        
        # Parse field-specific errors
        if 'username already exists' in error_msg.lower():
            field_errors['username'] = 'This username is already taken'
        elif 'email already exists' in error_msg.lower():
            field_errors['email'] = 'This email is already registered'
        elif 'password' in error_msg.lower():
            field_errors['password'] = error_msg
        else:
            # Generic validation error
            return jsonify({'error': error_msg}), 400
            
        return jsonify({
            'error': 'Registration failed',
            'field_errors': field_errors
        }), 400
        
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/login', methods=['POST'])
def login():
    """Login user - API endpoint"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        username = data.get('username')
        password = data.get('password')
        remember = data.get('remember', False)
        
        if not username or not password:
            return jsonify({
                'error': 'Username and password are required',
                'field_errors': {
                    'username': 'Username is required' if not username else None,
                    'password': 'Password is required' if not password else None
                }
            }), 400
        
        result = AuthService.login_user(username, password, remember)
        return jsonify({
            'message': 'Login successful',
            'data': result
        }), 200
        
    except ValueError as e:
        error_msg = str(e)
        field_errors = {}
        
        if 'invalid username' in error_msg.lower():
            field_errors['username'] = 'Username not found'
        elif 'invalid password' in error_msg.lower():
            field_errors['password'] = 'Incorrect password'
        elif 'invalid credentials' in error_msg.lower():
            field_errors['username'] = 'Invalid username or password'
            field_errors['password'] = 'Invalid username or password'
        
        return jsonify({
            'error': 'Login failed',
            'field_errors': field_errors
        }), 401
        
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user"""
    try:
        logout_user()
        return jsonify({'message': 'Logout successful'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        AuthService.refresh_token,
        user_id,
        success_message="Token refreshed successfully"
    )

@bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user profile"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        AuthService.get_user_profile,
        user_id
    )

@bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update user profile"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        AuthService.update_profile,
        user_id,
        request.get_json(),
        success_message="Profile updated successfully"
    )

@bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change user password"""
    user_id = get_jwt_identity()
    data = request.get_json()
    
    return BaseController.handle_request(
        AuthService.change_password,
        user_id,
        data.get('current_password'),
        data.get('new_password'),
        success_message="Password changed successfully"
    )

@bp.route('/verify-token', methods=['GET'])
@jwt_required()
def verify_token():
    """Verify if token is valid"""
    user_id = get_jwt_identity()
    return BaseController.handle_request(
        AuthService.get_user_profile,
        user_id
    )