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
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            if not user.is_teacher() and not user.is_admin():
                return jsonify({'error': 'Access denied. Teacher role required'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required():
    """Decorator to require admin role"""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            user_id = get_jwt_identity()
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
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            if not user.is_student():
                return jsonify({'error': 'Access denied. Student role required'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator