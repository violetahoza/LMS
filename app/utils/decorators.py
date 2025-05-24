from functools import wraps
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import User, UserRole

def teacher_required():
    """Decorator to require teacher role"""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            current_user = get_jwt_identity()
            
            try:
                user_id = int(current_user)
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid user ID format'}), 400
            
            user = User.query.get(user_id)
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
                
            # Allow both teachers and admins
            if not (user.role == UserRole.TEACHER or user.role == UserRole.ADMIN):
                return jsonify({'error': 'Teacher or admin access required'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required():
    """Decorator to require admin role"""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            user_id_str = get_jwt_identity()
            
            # Convert string to int
            try:
                user_id = int(user_id_str)
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid user ID'}), 400
            
            user = User.query.get(user_id)
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            if not user.is_admin():
                return jsonify({'error': 'Access denied. Admin role required'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def student_required():
    """Decorator to require student role"""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            user_id_str = get_jwt_identity()
            
            # Convert string to int
            try:
                user_id = int(user_id_str)
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid user ID'}), 400
            
            user = User.query.get(user_id)
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            if not user.is_student():
                return jsonify({'error': 'Access denied. Student role required'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator