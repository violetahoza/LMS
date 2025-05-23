# app/services/admin_service.py
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy import func, desc, or_
from app.models import db, User, Course, Enrollment, Quiz, QuizAttempt, Assignment, Achievement
from app.utils.base_controller import ValidationException, PermissionException, NotFoundException
from app.utils.helpers import calculate_course_statistics

class AdminService:
    """Service for admin-specific operations"""
    
    @staticmethod
    def get_dashboard() -> Dict[str, Any]:
        """Get admin dashboard statistics"""
        # User statistics
        total_users = User.query.count()
        total_students = User.query.filter_by(role='student').count()
        total_teachers = User.query.filter_by(role='teacher').count()
        active_users = User.query.filter_by(is_active=True).count()
        
        # Course statistics
        total_courses = Course.query.count()
        published_courses = Course.query.filter_by(is_published=True).count()
        
        # Enrollment statistics
        total_enrollments = Enrollment.query.count()
        active_enrollments = Enrollment.query.filter_by(status='active').count()
        completed_enrollments = Enrollment.query.filter_by(status='completed').count()
        
        # Quiz statistics
        total_quizzes = Quiz.query.count()
        total_quiz_attempts = QuizAttempt.query.count()
        
        # Recent activity (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_users = User.query.filter(User.created_at >= week_ago).count()
        recent_enrollments = Enrollment.query.filter(Enrollment.enrolled_at >= week_ago).count()
        recent_courses = Course.query.filter(Course.created_at >= week_ago).count()
        
        return {
            'users': {
                'total': total_users,
                'students': total_students,
                'teachers': total_teachers,
                'active': active_users,
                'recent': recent_users
            },
            'courses': {
                'total': total_courses,
                'published': published_courses,
                'recent': recent_courses
            },
            'enrollments': {
                'total': total_enrollments,
                'active': active_enrollments,
                'completed': completed_enrollments,
                'recent': recent_enrollments
            },
            'quizzes': {
                'total': total_quizzes,
                'attempts': total_quiz_attempts
            }
        }
    
    @staticmethod
    def get_users(page: int = 1, per_page: int = 20, role: Optional[str] = None,
                  active_only: bool = False, search: Optional[str] = None) -> Dict[str, Any]:
        """Get all users with filtering and pagination"""
        query = User.query
        
        # Apply filters
        if role:
            query = query.filter_by(role=role)
        
        if active_only:
            query = query.filter_by(is_active=True)
        
        if search:
            query = query.filter(
                or_(
                    User.username.contains(search),
                    User.email.contains(search),
                    User.full_name.contains(search)
                )
            )
        
        # Order by creation date
        query = query.order_by(desc(User.created_at))
        
        # Paginate
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        users = [user.to_dict() for user in pagination.items]
        
        return {
            'users': users,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }
    
    @staticmethod
    def get_user(user_id: int) -> Dict[str, Any]:
        """Get detailed user information"""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundException("User not found")
        
        user_data = user.to_dict()
        
        # Add detailed statistics based on role
        if user.is_student():
            enrollments = user.enrollments.all()
            user_data['detailed_stats'] = {
                'total_enrollments': len(enrollments),
                'active_enrollments': len([e for e in enrollments if e.status == 'active']),
                'completed_enrollments': len([e for e in enrollments if e.status == 'completed']),
                'quiz_attempts': user.quiz_attempts.count(),
                'assignments_submitted': user.assignment_submissions.count(),
                'achievements_earned': user.achievements.count()
            }
        elif user.is_teacher():
            courses = user.taught_courses.all()
            total_students = sum(course.get_enrollment_count() for course in courses)
            user_data['detailed_stats'] = {
                'total_courses': len(courses),
                'published_courses': len([c for c in courses if c.is_published]),
                'total_students': total_students,
                'total_quizzes': sum(course.quizzes.count() for course in courses),
                'total_assignments': sum(course.assignments.count() for course in courses)
            }
        
        return user_data
    
    @staticmethod
    def toggle_user_active(admin_id: int, user_id: int) -> Dict[str, Any]:
        """Toggle user active status"""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundException("User not found")
        
        # Don't allow deactivating other admins
        if user.is_admin() and user.id != admin_id:
            raise PermissionException("Cannot deactivate other admin users")
        
        user.is_active = not user.is_active
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        status = 'activated' if user.is_active else 'deactivated'
        return {
            'message': f'User {status} successfully',
            'user': user.to_dict()
        }
    
    @staticmethod
    def get_all_courses(page: int = 1, per_page: int = 20, category: Optional[str] = None,
                       published_only: bool = False) -> Dict[str, Any]:
        """Get all courses with detailed information"""
        query = Course.query
        
        if category:
            query = query.filter_by(category=category)
        
        if published_only:
            query = query.filter_by(is_published=True)
        
        query = query.order_by(desc(Course.created_at))
        
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        courses = []
        for course in pagination.items:
            course_data = course.to_dict()
            course_data['statistics'] = calculate_course_statistics(course)
            courses.append(course_data)
        
        return {
            'courses': courses,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }
    
    @staticmethod
    def toggle_course_published(course_id: int) -> Dict[str, Any]:
        """Toggle course published status"""
        course = Course.query.get(course_id)
        if not course:
            raise NotFoundException("Course not found")
        
        course.is_published = not course.is_published
        course.updated_at = datetime.utcnow()
        db.session.commit()
        
        status = 'published' if course.is_published else 'unpublished'
        return {
            'message': f'Course {status} successfully',
            'course': course.to_dict()
        }
    
    @staticmethod
    def get_user_activity_report(days: int = 30) -> Dict[str, Any]:
        """Get user activity report"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # User registrations over time
        user_registrations = db.session.query(
            func.date(User.created_at).label('date'),
            func.count(User.id).label('count')
        ).filter(
            User.created_at >= start_date
        ).group_by(
            func.date(User.created_at)
        ).order_by('date').all()
        
        # Course enrollments over time
        enrollments = db.session.query(
            func.date(Enrollment.enrolled_at).label('date'),
            func.count(Enrollment.id).label('count')
        ).filter(
            Enrollment.enrolled_at >= start_date
        ).group_by(
            func.date(Enrollment.enrolled_at)
        ).order_by('date').all()
        
        # Quiz attempts over time
        quiz_attempts = db.session.query(
            func.date(QuizAttempt.started_at).label('date'),
            func.count(QuizAttempt.id).label('count')
        ).filter(
            QuizAttempt.started_at >= start_date
        ).group_by(
            func.date(QuizAttempt.started_at)
        ).order_by('date').all()
        
        return {
            'period_days': days,
            'user_registrations': [
                {'date': str(item.date), 'count': item.count}
                for item in user_registrations
            ],
            'course_enrollments': [
                {'date': str(item.date), 'count': item.count}
                for item in enrollments
            ],
            'quiz_attempts': [
                {'date': str(item.date), 'count': item.count}
                for item in quiz_attempts
            ]
        }
    
    @staticmethod
    def get_course_performance_report() -> Dict[str, Any]:
        """Get course performance report"""
        courses = Course.query.filter_by(is_published=True).all()
        
        course_performance = []
        for course in courses:
            stats = calculate_course_statistics(course)
            
            # Get average quiz scores for the course
            avg_quiz_score = db.session.query(
                func.avg(QuizAttempt.score)
            ).join(Quiz).filter(
                Quiz.course_id == course.id,
                QuizAttempt.status == 'completed'
            ).scalar() or 0
            
            course_performance.append({
                'course_id': course.id,
                'course_title': course.title,
                'teacher_name': course.teacher.full_name,
                'category': course.category,
                'total_students': stats['total_students'],
                'completion_rate': stats['completion_rate'],
                'average_quiz_score': round(avg_quiz_score, 2),
                'total_lessons': stats['total_lessons'],
                'total_quizzes': stats['total_quizzes'],
                'average_completion_days': stats['average_completion_days']
            })
        
        # Sort by completion rate
        course_performance.sort(key=lambda x: x['completion_rate'], reverse=True)
        
        return {
            'courses': course_performance,
            'total_courses': len(course_performance)
        }
    
    @staticmethod
    def get_achievements() -> Dict[str, Any]:
        """Get all achievements"""
        achievements = Achievement.query.all()
        
        achievements_data = []
        for achievement in achievements:
            achievement_data = {
                'id': achievement.id,
                'name': achievement.name,
                'description': achievement.description,
                'badge_icon': achievement.badge_icon,
                'points_value': achievement.points_value,
                'criteria_type': achievement.criteria_type,
                'criteria_value': achievement.criteria_value,
                'earned_count': achievement.student_achievements.count()
            }
            achievements_data.append(achievement_data)
        
        return {
            'achievements': achievements_data,
            'total': len(achievements_data)
        }
    
    @staticmethod
    def create_achievement(achievement_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new achievement"""
        required_fields = ['name', 'description', 'criteria_type', 'criteria_value']
        for field in required_fields:
            if field not in achievement_data:
                raise ValidationException(f'{field} is required')
        
        achievement = Achievement(
            name=achievement_data['name'],
            description=achievement_data['description'],
            badge_icon=achievement_data.get('badge_icon'),
            points_value=achievement_data.get('points_value', 0),
            criteria_type=achievement_data['criteria_type'],
            criteria_value=achievement_data['criteria_value']
        )
        
        db.session.add(achievement)
        db.session.commit()
        
        return {
            'message': 'Achievement created successfully',
            'achievement': {
                'id': achievement.id,
                'name': achievement.name,
                'description': achievement.description,
                'points_value': achievement.points_value
            }
        }