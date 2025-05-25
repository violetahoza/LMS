from datetime import datetime
from typing import Dict, Any, List
from app.models import db, User, Achievement, StudentAchievement, QuizAttempt, Enrollment, LessonProgress
from app.utils.base_controller import ValidationException, PermissionException, NotFoundException
from app.utils.helpers import check_achievement_criteria
from app.services.notification_service import NotificationService

class AchievementService:
    """Service for achievement-related operations"""
    
    @staticmethod
    def get_student_achievements(student_id: int) -> Dict[str, Any]:
        """Get all achievements earned by a student"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise PermissionException("Only students can access achievements")
        
        earned_achievements = db.session.query(StudentAchievement, Achievement).join(
            Achievement, StudentAchievement.achievement_id == Achievement.id
        ).filter(StudentAchievement.student_id == student_id).all()
        
        achievements_data = []
        total_points = 0
        
        for student_achievement, achievement in earned_achievements:
            achievement_dict = {
                'id': achievement.id,
                'name': achievement.name,
                'description': achievement.description,
                'badge_icon': achievement.badge_icon,
                'points': achievement.points_value,
                'earned_at': student_achievement.earned_at.isoformat() if student_achievement.earned_at else None
            }
            achievements_data.append(achievement_dict)
            total_points += achievement.points_value or 0
        
        return {
            'achievements': achievements_data,
            'total_achievements': len(achievements_data),
            'total_points': total_points
        }
    
    @staticmethod
    def get_available_achievements(student_id: int) -> Dict[str, Any]:
        """Get achievements that student hasn't earned yet"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise PermissionException("Only students can access achievements")
        
        earned_ids = db.session.query(StudentAchievement.achievement_id).filter_by(
            student_id=student_id
        ).subquery()
        
        available = Achievement.query.filter(
            ~Achievement.id.in_(earned_ids)
        ).all()
        
        available_data = []
        for achievement in available:
            meets_criteria = check_achievement_criteria(user, achievement)
            
            achievement_dict = {
                'id': achievement.id,
                'name': achievement.name,
                'description': achievement.description,
                'badge_icon': achievement.badge_icon,
                'points': achievement.points_value,
                'criteria_type': achievement.criteria_type,
                'criteria_value': achievement.criteria_value,
                'can_earn': meets_criteria
            }
            available_data.append(achievement_dict)
        
        return {
            'available_achievements': available_data,
            'total_available': len(available_data)
        }
    
    @staticmethod
    def check_quiz_achievement(student_id: int, attempt_id: int) -> List[Achievement]:
        """Check and award quiz-related achievements"""
        attempt = QuizAttempt.query.get(attempt_id)
        if not attempt or attempt.student_id != student_id:
            return []
        
        achievements_earned = []
        
        score_achievements = Achievement.query.filter_by(
            criteria_type='quiz_score'
        ).all()
        
        for achievement in score_achievements:
            existing = StudentAchievement.query.filter_by(
                student_id=student_id,
                achievement_id=achievement.id
            ).first()
            
            if not existing and attempt.score >= achievement.criteria_value:
                student_achievement = StudentAchievement(
                    student_id=student_id,
                    achievement_id=achievement.id
                )
                db.session.add(student_achievement)
                achievements_earned.append(achievement)
        
        if achievements_earned:
            db.session.commit()
        
        return achievements_earned
    
    @staticmethod
    def check_course_completion_achievement(student_id: int, course_id: int) -> List[Achievement]:
        """Check and award course completion achievements"""
        achievements_earned = []
        
        # Course completion achievements
        completion_achievements = Achievement.query.filter_by(
            criteria_type='course_completion'
        ).all()
        
        # Get completed courses count
        completed_count = Enrollment.query.filter_by(
            student_id=student_id,
            status='completed'
        ).count()
        
        for achievement in completion_achievements:
            # Check if already earned
            existing = StudentAchievement.query.filter_by(
                student_id=student_id,
                achievement_id=achievement.id
            ).first()
            
            if not existing and completed_count >= achievement.criteria_value:
                student_achievement = StudentAchievement(
                    student_id=student_id,
                    achievement_id=achievement.id
                )
                db.session.add(student_achievement)
                achievements_earned.append(achievement)
        
        if achievements_earned:
            db.session.commit()
        
        return achievements_earned
    
    @staticmethod
    def check_participation_achievement(student_id: int) -> List[Achievement]:
        """Check and award participation achievements"""
        achievements_earned = []
        
        # Participation achievements (based on lesson views)
        participation_achievements = Achievement.query.filter_by(
            criteria_type='participation'
        ).all()
        
        # Get lesson participation count
        lesson_count = LessonProgress.query.filter_by(
            student_id=student_id
        ).count()
        
        for achievement in participation_achievements:
            # Check if already earned
            existing = StudentAchievement.query.filter_by(
                student_id=student_id,
                achievement_id=achievement.id
            ).first()
            
            if not existing and lesson_count >= achievement.criteria_value:
                student_achievement = StudentAchievement(
                    student_id=student_id,
                    achievement_id=achievement.id
                )
                db.session.add(student_achievement)
                achievements_earned.append(achievement)
        
        if achievements_earned:
            db.session.commit()
        
        return achievements_earned
    
    @staticmethod
    def create_default_achievements():
        """Create default achievements for the platform"""
        default_achievements = [
            {
                'name': 'First Steps',
                'description': 'Complete your first lesson',
                'criteria_type': 'participation',
                'criteria_value': 1,
                'points_value': 10,
                'badge_icon': 'fas fa-baby'
            },
            {
                'name': 'Getting Started',
                'description': 'Complete 5 lessons',
                'criteria_type': 'participation',
                'criteria_value': 5,
                'points_value': 25,
                'badge_icon': 'fas fa-play'
            },
            {
                'name': 'Dedicated Learner',
                'description': 'Complete 25 lessons',
                'criteria_type': 'participation',
                'criteria_value': 25,
                'points_value': 100,
                'badge_icon': 'fas fa-book-reader'
            },
            {
                'name': 'Perfect Score',
                'description': 'Score 100% on a quiz',
                'criteria_type': 'quiz_score',
                'criteria_value': 100,
                'points_value': 50,
                'badge_icon': 'fas fa-star'
            },
            {
                'name': 'High Achiever',
                'description': 'Score 90% or higher on a quiz',
                'criteria_type': 'quiz_score',
                'criteria_value': 90,
                'points_value': 25,
                'badge_icon': 'fas fa-trophy'
            },
            {
                'name': 'Course Completer',
                'description': 'Complete your first course',
                'criteria_type': 'course_completion',
                'criteria_value': 1,
                'points_value': 100,
                'badge_icon': 'fas fa-graduation-cap'
            },
            {
                'name': 'Scholar',
                'description': 'Complete 3 courses',
                'criteria_type': 'course_completion',
                'criteria_value': 3,
                'points_value': 300,
                'badge_icon': 'fas fa-user-graduate'
            },
            {
                'name': 'Master Learner',
                'description': 'Complete 10 courses',
                'criteria_type': 'course_completion',
                'criteria_value': 10,
                'points_value': 1000,
                'badge_icon': 'fas fa-crown'
            }
        ]
        
        for achievement_data in default_achievements:
            existing = Achievement.query.filter_by(name=achievement_data['name']).first()
            if not existing:
                achievement = Achievement(**achievement_data)
                db.session.add(achievement)
        
        try:
            db.session.commit()
            print("✅ Default achievements created")
        except Exception as e:
            db.session.rollback()
            print(f"⚠️ Error creating achievements: {e}")
    
    @staticmethod
    def award_achievement(student_id: int, achievement_id: int) -> Dict[str, Any]:
        """Manually award an achievement to a student"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise ValidationException("Invalid student")
        
        achievement = Achievement.query.get(achievement_id)
        if not achievement:
            raise NotFoundException("Achievement not found")
        
        # Check if already awarded
        existing = StudentAchievement.query.filter_by(
            student_id=student_id,
            achievement_id=achievement_id
        ).first()
        
        if existing:
            raise ValidationException("Achievement already awarded")
        
        student_achievement = StudentAchievement(
            student_id=student_id,
            achievement_id=achievement_id
        )
        
        db.session.add(student_achievement)
        db.session.commit()
        
        return {
            'message': 'Achievement awarded successfully',
            'achievement': {
                'name': achievement.name,
                'description': achievement.description,
                'points': achievement.points_value
            }
        }