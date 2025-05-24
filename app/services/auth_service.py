from datetime import datetime
from typing import Dict, Any, Tuple
from flask_jwt_extended import create_access_token, create_refresh_token
from app.models import db, User, UserRole
from app.utils.validators import validate_email, validate_password, validate_username, validate_phone
from app.utils.base_controller import ValidationException, NotFoundException

class AuthService:
    """Service for authentication operations"""
    
    @staticmethod
    def register_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new user"""
        required_fields = ['username', 'email', 'password', 'full_name', 'role']
        for field in required_fields:
            if field not in user_data or not user_data[field]:
                raise ValidationException(f'{field} is required')
        
        if not validate_email(user_data['email']):
            raise ValidationException('Invalid email format')
        
        is_valid, message = validate_password(user_data['password'])
        if not is_valid:
            raise ValidationException(message)
        
        is_valid, message = validate_username(user_data['username'])
        if not is_valid:
            raise ValidationException(message)
        
        if User.query.filter_by(email=user_data['email']).first():
            raise ValidationException('Email already registered')
        
        if User.query.filter_by(username=user_data['username']).first():
            raise ValidationException('Username already taken')
        
        try:
            role = UserRole(user_data['role'].lower())
        except ValueError:
            raise ValidationException('Invalid role. Must be admin, teacher, or student')
        
        if 'phone' in user_data and user_data['phone'] and not validate_phone(user_data['phone']):
            raise ValidationException('Invalid phone number format')
        
        if 'age' in user_data and user_data['age']:
            try:
                age = int(user_data['age'])
                if age < 13 or age > 120:
                    raise ValidationException('Age must be between 13 and 120')
            except ValueError:
                raise ValidationException('Age must be a valid number')
        
        user = User(
            username=user_data['username'],
            email=user_data['email'],
            full_name=user_data['full_name'],
            role=role,
            phone=user_data.get('phone'),
            age=user_data.get('age')
        )
        user.set_password(user_data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        return {
            'message': 'User registered successfully',
            'user': user.to_dict()
        }
    
    @staticmethod
    def login_user(username: str, password: str, remember: bool = False) -> Dict[str, Any]:
        """Login user and return tokens"""
        if not username or not password:
            raise ValidationException('Username and password are required')
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            raise ValidationException('Invalid username or password')
        
        if not user.is_active:
            raise ValidationException('Account is deactivated')
        
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))
        
        return {
            'message': 'Login successful',
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user.to_dict()
        }
    
    @staticmethod
    def refresh_token(user_id: str) -> Dict[str, Any]:
        """Refresh access token"""
        try:
            user_id_int = int(user_id)
        except ValueError:
            raise NotFoundException('Invalid user ID')
            
        user = User.query.get(user_id_int)
        
        if not user or not user.is_active:
            raise NotFoundException('User not found or inactive')
        
        new_token = create_access_token(identity=str(user.id))
        
        return {
            'access_token': new_token,
            'user': user.to_dict()
        }
    
    @staticmethod
    def get_user_profile(user_id: str) -> Dict[str, Any]:
        """Get user profile with statistics"""
        try:
            user_id_int = int(user_id)
        except ValueError:
            raise NotFoundException('Invalid user ID')
            
        user = User.query.get(user_id_int)
        if not user:
            raise NotFoundException('User not found')
        
        profile_data = user.to_dict()
        
        if user.is_student():
            enrollments = user.enrollments.all()
            profile_data['stats'] = {
                'enrolled_courses': user.enrollments.filter_by(status='active').count(),
                'completed_courses': user.enrollments.filter_by(status='completed').count(),
                'total_achievements': user.achievements.count()
            }
        elif user.is_teacher():
            total_students = 0
            for course in user.taught_courses:
                total_students += course.get_enrollment_count()
            
            profile_data['stats'] = {
                'total_courses': user.taught_courses.count(),
                'published_courses': user.taught_courses.filter_by(is_published=True).count(),
                'total_students': total_students
            }
        
        return profile_data
    
    @staticmethod
    def update_profile(user_id: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user profile"""
        try:
            user_id_int = int(user_id)
        except ValueError:
            raise NotFoundException('Invalid user ID')
            
        user = User.query.get(user_id_int)
        if not user:
            raise NotFoundException('User not found')
        
        allowed_fields = ['full_name', 'phone', 'age']
        for field in allowed_fields:
            if field in profile_data:
                if field == 'phone' and profile_data[field] and not validate_phone(profile_data[field]):
                    raise ValidationException('Invalid phone number format')
                if field == 'age' and profile_data[field]:
                    try:
                        age = int(profile_data[field])
                        if age < 13 or age > 120:
                            raise ValidationException('Age must be between 13 and 120')
                        profile_data[field] = age
                    except ValueError:
                        raise ValidationException('Age must be a valid number')
                
                setattr(user, field, profile_data[field])
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return {
            'message': 'Profile updated successfully',
            'user': user.to_dict()
        }
    
    @staticmethod
    def change_password(user_id: str, current_password: str, new_password: str) -> Dict[str, str]:
        """Change user password"""
        try:
            user_id_int = int(user_id)
        except ValueError:
            raise NotFoundException('Invalid user ID')
            
        user = User.query.get(user_id_int)
        if not user:
            raise NotFoundException('User not found')
        
        if not current_password or not new_password:
            raise ValidationException('Current password and new password are required')
        
        if not user.check_password(current_password):
            raise ValidationException('Current password is incorrect')
        
        is_valid, message = validate_password(new_password)
        if not is_valid:
            raise ValidationException(message)
        
        user.set_password(new_password)
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return {'message': 'Password changed successfully'}