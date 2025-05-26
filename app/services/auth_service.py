from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from flask_jwt_extended import create_access_token, create_refresh_token
from app.models import db, User, UserRole
from app.utils.base_controller import ValidationException, PermissionException, NotFoundException
from app.utils.validators import validate_email, validate_password, validate_phone, validate_username

class AuthService:
    """Service for authentication-related operations"""
    
    @staticmethod
    def register_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new user"""
        try:
            required_fields = ['username', 'email', 'password', 'full_name', 'role']
            for field in required_fields:
                if field not in user_data or not user_data[field]:
                    raise ValidationException(f'{field} is required')
            
            username = user_data['username'].strip()
            is_valid, message = validate_username(username)
            if not is_valid:
                raise ValidationException(message)
            
            if User.query.filter_by(username=username).first():
                raise ValidationException('Username already exists')
            
            email = user_data['email'].strip().lower()
            if not validate_email(email):
                raise ValidationException('Invalid email format')
            
            if User.query.filter_by(email=email).first():
                raise ValidationException('Email already exists')
            
            password = user_data['password']
            is_valid, message = validate_password(password)
            if not is_valid:
                raise ValidationException(message)
            
            role_str = user_data['role'].lower()
            try:
                if role_str == 'student':
                    role = UserRole.STUDENT
                elif role_str == 'teacher':
                    role = UserRole.TEACHER
                elif role_str == 'admin':
                    role = UserRole.ADMIN
                else:
                    raise ValidationException('Invalid role')
            except Exception:
                raise ValidationException('Invalid role')
            
            phone = user_data.get('phone', '').strip()
            if phone and not validate_phone(phone):
                raise ValidationException('Invalid phone number format')
            
            age = user_data.get('age')
            if age is not None:
                try:
                    age = int(age)
                    if age < 13 or age > 90:
                        raise ValidationException('Age must be between 13 and 90')
                except (ValueError, TypeError):
                    raise ValidationException('Age must be a number')
            
            user = User(
                username=username,
                email=email,
                full_name=user_data['full_name'].strip(),
                role=role,
                phone=phone if phone else None,
                age=age,
                is_active=True
            )
            
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            return {
                'message': 'User registered successfully',
                'user': user.to_dict()
            }
            
        except ValidationException:
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Registration failed: {str(e)}")
    
    @staticmethod
    def login_user(login_data: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate user and return tokens"""
        try:
            username = login_data.get('username', '').strip()
            password = login_data.get('password', '')
            remember = login_data.get('remember', False)
            
            if not username or not password:
                raise ValidationException('Username and password are required')
            
            user = User.query.filter(
                (User.username == username) | (User.email == username.lower())
            ).first()
            
            if not user:
                raise ValidationException('Invalid username or password')
            
            if not user.is_active:
                raise ValidationException('Account is deactivated')
            
            if not user.check_password(password):
                raise ValidationException('Invalid username or password')
            
            expires_delta = timedelta(days=30) if remember else timedelta(hours=24)
            access_token = create_access_token(
                identity=str(user.id),
                expires_delta=expires_delta
            )
            refresh_token = create_refresh_token(
                identity=str(user.id),
                expires_delta=timedelta(days=30)
            )
            
            return {
                'message': 'Login successful',
                'user': user.to_dict(),
                'access_token': access_token,
                'refresh_token': refresh_token
            }
            
        except ValidationException:
            raise
        except Exception as e:
            raise Exception(f"Login failed: {str(e)}")
    
    @staticmethod
    def get_user_profile(user_id: int) -> Dict[str, Any]:
        """Get user profile information"""
        try:
            user = User.query.get(user_id)
            if not user:
                raise NotFoundException("User not found")
            
            stats = AuthService._get_user_stats(user)
            
            user_data = user.to_dict()
            user_data['stats'] = stats
            
            return user_data
            
        except Exception as e:
            raise Exception(f"Failed to get profile: {str(e)}")
    
    @staticmethod
    def update_user_profile(user_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user profile"""
        try:
            user = User.query.get(user_id)
            if not user:
                raise NotFoundException("User not found")
            
            allowed_fields = ['full_name', 'phone', 'age']
            
            for field in allowed_fields:
                if field in update_data:
                    value = update_data[field]
                    
                    if field == 'full_name':
                        if not value or not value.strip():
                            raise ValidationException('Full name cannot be empty')
                        setattr(user, field, value.strip())
                    
                    elif field == 'phone':
                        if value and not validate_phone(value):
                            raise ValidationException('Invalid phone number format')
                        setattr(user, field, value.strip() if value else None)
                    
                    elif field == 'age':
                        if value is not None:
                            try:
                                age = int(value)
                                if age < 13 or age > 120:
                                    raise ValidationException('Age must be between 13 and 120')
                                setattr(user, field, age)
                            except (ValueError, TypeError):
                                raise ValidationException('Age must be a number')
                        else:
                            setattr(user, field, None)
            
            user.updated_at = datetime.now()
            db.session.commit()
            
            return {
                'message': 'Profile updated successfully',
                'user': user.to_dict()
            }
            
        except ValidationException:
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to update profile: {str(e)}")
    
    @staticmethod
    def change_password(user_id: int, password_data: Dict[str, Any]) -> Dict[str, str]:
        """Change user password"""
        try:
            user = User.query.get(user_id)
            if not user:
                raise NotFoundException("User not found")
            
            current_password = password_data.get('current_password', '')
            new_password = password_data.get('new_password', '')
            
            if not current_password or not new_password:
                raise ValidationException('Current password and new password are required')
            
            if not user.check_password(current_password):
                raise ValidationException('Current password is incorrect')
            
            is_valid, message = validate_password(new_password)
            if not is_valid:
                raise ValidationException(message)
            
            user.set_password(new_password)
            user.updated_at = datetime.now()
            db.session.commit()
            
            return {'message': 'Password changed successfully'}
            
        except ValidationException:
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to change password: {str(e)}")
    
    @staticmethod
    def _get_user_stats(user: User) -> Dict[str, Any]:
        """Get role-specific user statistics"""
        stats = {}
        
        try:
            if user.is_student():
                from app.models import Enrollment, QuizAttempt, AssignmentSubmission, StudentAchievement
                
                enrolled_courses = Enrollment.query.filter_by(student_id=user.id).count()
                completed_courses = Enrollment.query.filter_by(
                    student_id=user.id, 
                    status='completed'
                ).count()
                
                quiz_attempts = QuizAttempt.query.filter_by(student_id=user.id).count()
                assignment_submissions = AssignmentSubmission.query.filter_by(student_id=user.id).count()
                total_achievements = StudentAchievement.query.filter_by(student_id=user.id).count()
                
                stats = {
                    'enrolled_courses': enrolled_courses,
                    'completed_courses': completed_courses,
                    'quiz_attempts': quiz_attempts,
                    'assignment_submissions': assignment_submissions,
                    'total_achievements': total_achievements
                }
                
            elif user.is_teacher():
                total_courses = user.taught_courses.count()
                total_students = sum(course.get_enrollment_count() for course in user.taught_courses)
                
                stats = {
                    'total_courses': total_courses,
                    'total_students': total_students
                }
                
            elif user.is_admin():
                from app.models import Course, Enrollment
                
                total_users = User.query.count()
                total_courses = Course.query.count()
                total_enrollments = Enrollment.query.count()
                
                stats = {
                    'total_users': total_users,
                    'total_courses': total_courses,
                    'total_enrollments': total_enrollments
                }
                
        except Exception as e:
            print(f"Error calculating user stats: {e}")
            stats = {}
        
        return stats