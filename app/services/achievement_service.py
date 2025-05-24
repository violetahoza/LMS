from datetime import datetime, timedelta
from app.models import db, Achievement, StudentAchievement, User, QuizAttempt, Enrollment, LessonProgress
from app.utils.helpers import check_achievement_criteria

class AchievementService:
    """Service class for achievement/badge management"""
    
    @staticmethod
    def check_and_award_achievements(student_id, trigger_type=None):
        """Check and award achievements based on student progress"""
        student = User.query.get(student_id)
        if not student or not student.is_student():
            return []
        
        achievements = Achievement.query.all()
        
        earned_achievement_ids = set(
            sa.achievement_id for sa in StudentAchievement.query.filter_by(
                student_id=student_id
            ).all()
        )
        
        newly_earned = []
        
        for achievement in achievements:
            if achievement.id in earned_achievement_ids:
                continue
            
            if trigger_type and achievement.criteria_type != trigger_type:
                continue
            
            if check_achievement_criteria(student, achievement):
                student_achievement = StudentAchievement(
                    student_id=student_id,
                    achievement_id=achievement.id
                )
                db.session.add(student_achievement)
                newly_earned.append(achievement)
        
        if newly_earned:
            db.session.commit()
        
        return newly_earned
    
    @staticmethod
    def check_course_completion_achievement(student_id, course_id):
        """Check for course completion achievements"""
        enrollment = Enrollment.query.filter_by(
            student_id=student_id,
            course_id=course_id,
            status='completed'
        ).first()
        
        if not enrollment:
            return []
        
        return AchievementService.check_and_award_achievements(
            student_id, 
            trigger_type='course_completion'
        )
    
    @staticmethod
    def check_quiz_achievement(student_id, quiz_attempt_id):
        """Check for quiz-related achievements"""
        attempt = QuizAttempt.query.get(quiz_attempt_id)
        if not attempt or attempt.student_id != student_id:
            return []
        
        return AchievementService.check_and_award_achievements(
            student_id,
            trigger_type='quiz_score'
        )
    
    @staticmethod
    def check_participation_achievement(student_id):
        """Check for participation achievements"""
        return AchievementService.check_and_award_achievements(
            student_id,
            trigger_type='participation'
        )
    
    @staticmethod
    def check_streak_achievement(student_id):
        """Check for streak achievements"""
        recent_progress = LessonProgress.query.filter_by(
            student_id=student_id
        ).filter(
            LessonProgress.viewed_at >= datetime.utcnow() - timedelta(days=30)
        ).order_by(LessonProgress.viewed_at.desc()).all()
        
        if not recent_progress:
            return []
        
        streak = 1
        last_date = recent_progress[0].viewed_at.date()
        
        for progress in recent_progress[1:]:
            current_date = progress.viewed_at.date()
            if (last_date - current_date).days == 1:
                streak += 1
                last_date = current_date
            else:
                break
        
        streak_achievements = Achievement.query.filter_by(
            criteria_type='streak'
        ).filter(
            Achievement.criteria_value <= streak
        ).all()
        
        earned = []
        for achievement in streak_achievements:
            existing = StudentAchievement.query.filter_by(
                student_id=student_id,
                achievement_id=achievement.id
            ).first()
            
            if not existing:
                student_achievement = StudentAchievement(
                    student_id=student_id,
                    achievement_id=achievement.id
                )
                db.session.add(student_achievement)
                earned.append(achievement)
        
        if earned:
            db.session.commit()
        
        return earned
    
    @staticmethod
    def get_student_achievements(student_id):
        """Get all achievements earned by a student"""
        student_achievements = StudentAchievement.query.filter_by(
            student_id=student_id
        ).order_by(StudentAchievement.earned_at.desc()).all()
        
        achievements_data = []
        total_points = 0
        
        for sa in student_achievements:
            achievement = sa.achievement
            achievements_data.append({
                'id': achievement.id,
                'name': achievement.name,
                'description': achievement.description,
                'badge_icon': achievement.badge_icon,
                'points_value': achievement.points_value,
                'earned_at': sa.earned_at.isoformat() if sa.earned_at else None
            })
            total_points += achievement.points_value
        
        return {
            'achievements': achievements_data,
            'total_achievements': len(achievements_data),
            'total_points': total_points
        }
    
    @staticmethod
    def get_available_achievements(student_id):
        """Get achievements not yet earned by a student"""
        earned_ids = [
            sa.achievement_id for sa in StudentAchievement.query.filter_by(
                student_id=student_id
            ).all()
        ]
        
        available = Achievement.query.filter(
            ~Achievement.id.in_(earned_ids)
        ).all()
        
        return [
            {
                'id': a.id,
                'name': a.name,
                'description': a.description,
                'badge_icon': a.badge_icon,
                'points_value': a.points_value,
                'criteria_type': a.criteria_type,
                'criteria_value': a.criteria_value
            }
            for a in available
        ]
    
    @staticmethod
    def get_leaderboard(limit=10):
        """Get achievement leaderboard"""
        leaderboard = db.session.query(
            User.id,
            User.full_name,
            User.username,
            db.func.sum(Achievement.points_value).label('total_points'),
            db.func.count(StudentAchievement.id).label('achievement_count')
        ).join(
            StudentAchievement, User.id == StudentAchievement.student_id
        ).join(
            Achievement, StudentAchievement.achievement_id == Achievement.id
        ).filter(
            User.role == 'student'
        ).group_by(
            User.id
        ).order_by(
            db.func.sum(Achievement.points_value).desc()
        ).limit(limit).all()
        
        return [
            {
                'rank': idx + 1,
                'student_id': entry.id,
                'student_name': entry.full_name,
                'username': entry.username,
                'total_points': entry.total_points,
                'achievement_count': entry.achievement_count
            }
            for idx, entry in enumerate(leaderboard)
        ]
    
    @staticmethod
    def create_achievement(name, description, badge_icon, points_value, criteria_type, criteria_value):
        """Create a new achievement"""
        achievement = Achievement(
            name=name,
            description=description,
            badge_icon=badge_icon,
            points_value=points_value,
            criteria_type=criteria_type,
            criteria_value=criteria_value
        )
        
        db.session.add(achievement)
        db.session.commit()
        
        return achievement