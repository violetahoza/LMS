from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from sqlalchemy import desc, func

from app.models import db, User, Enrollment, LessonProgress, QuizAttempt, AssignmentSubmission, Certificate
from app.services.achievement_service import AchievementService
from app.services.certificate_service import CertificateService
from app.utils.decorators import student_required

bp = Blueprint('student', __name__, url_prefix='/api/student')

@bp.route('/dashboard', methods=['GET'])
@student_required()
def get_dashboard():
    """Get student dashboard data"""
    try:
        user_id = get_jwt_identity()
        
        # Get enrollments
        active_enrollments = Enrollment.query.filter_by(
            student_id=user_id,
            status='active'
        ).all()
        
        completed_enrollments = Enrollment.query.filter_by(
            student_id=user_id,
            status='completed'
        ).all()
        
        # Calculate overall progress
        total_progress = 0
        if active_enrollments:
            total_progress = sum(e.progress_percentage for e in active_enrollments) / len(active_enrollments)
        
        # Get recent activity
        recent_lessons = LessonProgress.query.filter_by(
            student_id=user_id
        ).order_by(desc(LessonProgress.viewed_at)).limit(5).all()
        
        recent_quiz_attempts = QuizAttempt.query.filter_by(
            student_id=user_id
        ).order_by(desc(QuizAttempt.started_at)).limit(5).all()
        
        # Get achievements
        achievements_data = AchievementService.get_student_achievements(user_id)
        
        # Get upcoming assignments (due in next 7 days)
        week_from_now = datetime.utcnow() + timedelta(days=7)
        from app.models import Assignment
        upcoming_assignments = Assignment.query.join(
            Enrollment, Assignment.course_id == Enrollment.course_id
        ).filter(
            Enrollment.student_id == user_id,
            Enrollment.status == 'active',
            Assignment.due_date <= week_from_now,
            Assignment.due_date >= datetime.utcnow()
        ).order_by(Assignment.due_date).all()
        
        # Format recent activity
        recent_activity = []
        
        for lesson in recent_lessons:
            recent_activity.append({
                'type': 'lesson',
                'title': f"Viewed: {lesson.lesson.title}",
                'course': lesson.lesson.course.title,
                'timestamp': lesson.viewed_at.isoformat() if lesson.viewed_at else None
            })
        
        for attempt in recent_quiz_attempts:
            recent_activity.append({
                'type': 'quiz',
                'title': f"Quiz: {attempt.quiz.title}",
                'course': attempt.quiz.course.title,
                'score': attempt.score,
                'timestamp': attempt.started_at.isoformat() if attempt.started_at else None
            })
        
        # Sort recent activity by timestamp
        recent_activity.sort(key=lambda x: x['timestamp'] or '', reverse=True)
        recent_activity = recent_activity[:10]  # Limit to 10 items
        
        return jsonify({
            'stats': {
                'active_courses': len(active_enrollments),
                'completed_courses': len(completed_enrollments),
                'overall_progress': round(total_progress, 1),
                'total_achievements': achievements_data['total_achievements'],
                'achievement_points': achievements_data['total_points']
            },
            'active_courses': [
                {
                    'id': e.course.id,
                    'title': e.course.title,
                    'progress': e.progress_percentage,
                    'teacher': e.course.teacher.full_name,
                    'enrolled_at': e.enrolled_at.isoformat() if e.enrolled_at else None
                }
                for e in active_enrollments
            ],
            'recent_activity': recent_activity,
            'upcoming_assignments': [
                {
                    'id': a.id,
                    'title': a.title,
                    'course': a.course.title,
                    'due_date': a.due_date.isoformat() if a.due_date else None,
                    'days_remaining': (a.due_date - datetime.utcnow()).days if a.due_date else 0
                }
                for a in upcoming_assignments
            ],
            'achievements': achievements_data['achievements'][:5]  # Latest 5 achievements
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/progress', methods=['GET'])
@student_required()
def get_progress():
    """Get detailed student progress"""
    try:
        user_id = get_jwt_identity()
        
        # Get all enrollments
        enrollments = Enrollment.query.filter_by(student_id=user_id).all()
        
        progress_data = []
        for enrollment in enrollments:
            course = enrollment.course
            
            # Get lesson progress
            total_lessons = course.lessons.count()
            completed_lessons = LessonProgress.query.filter_by(
                student_id=user_id
            ).join(
                'lesson'
            ).filter_by(course_id=course.id).filter(
                LessonProgress.completed_at.isnot(None)
            ).count()
            
            # Get quiz progress
            course_quizzes = course.quizzes.all()
            quiz_progress = []
            
            for quiz in course_quizzes:
                best_attempt = QuizAttempt.query.filter_by(
                    student_id=user_id,
                    quiz_id=quiz.id,
                    status='completed'
                ).order_by(desc(QuizAttempt.score)).first()
                
                quiz_progress.append({
                    'quiz_id': quiz.id,
                    'quiz_title': quiz.title,
                    'best_score': best_attempt.score if best_attempt else None,
                    'passed': best_attempt.score >= quiz.passing_score if best_attempt else False,
                    'attempts': QuizAttempt.query.filter_by(
                        student_id=user_id, quiz_id=quiz.id
                    ).count()
                })
            
            # Get assignment progress
            course_assignments = course.assignments.all()
            assignment_progress = []
            
            for assignment in course_assignments:
                submission = AssignmentSubmission.query.filter_by(
                    student_id=user_id,
                    assignment_id=assignment.id
                ).first()
                
                assignment_progress.append({
                    'assignment_id': assignment.id,
                    'assignment_title': assignment.title,
                    'submitted': submission is not None,
                    'grade': submission.grade if submission else None,
                    'status': submission.status if submission else 'not_submitted'
                })
            
            progress_data.append({
                'course': course.to_dict(),
                'enrollment': enrollment.to_dict(),
                'lesson_progress': {
                    'completed': completed_lessons,
                    'total': total_lessons,
                    'percentage': (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0
                },
                'quiz_progress': quiz_progress,
                'assignment_progress': assignment_progress
            })
        
        return jsonify({
            'courses': progress_data,
            'total_courses': len(progress_data)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/achievements', methods=['GET'])
@student_required()
def get_achievements():
    """Get student achievements"""
    try:
        user_id = get_jwt_identity()
        
        earned_achievements = AchievementService.get_student_achievements(user_id)
        available_achievements = AchievementService.get_available_achievements(user_id)
        
        return jsonify({
            'earned': earned_achievements,
            'available': available_achievements
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/certificates', methods=['GET'])
@student_required()
def get_certificates():
    """Get student certificates"""
    try:
        user_id = get_jwt_identity()
        
        certificates = CertificateService.get_student_certificates(user_id)
        
        return jsonify({
            'certificates': certificates,
            'total': len(certificates)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/certificates/request/<int:course_id>', methods=['POST'])
@student_required()
def request_certificate(course_id):
    """Request certificate for completed course"""
    try:
        user_id = get_jwt_identity()
        
        # Check if already has certificate
        existing_cert = Certificate.query.filter_by(
            student_id=user_id,
            course_id=course_id
        ).first()
        
        if existing_cert:
            return jsonify({
                'message': 'Certificate already exists',
                'certificate': existing_cert.to_dict()
            }), 200
        
        # Generate certificate
        certificate = CertificateService.generate_certificate(user_id, course_id)
        
        return jsonify({
            'message': 'Certificate generated successfully',
            'certificate': certificate.to_dict()
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/study-streak', methods=['GET'])
@student_required()
def get_study_streak():
    """Get student study streak information"""
    try:
        user_id = get_jwt_identity()
        
        # Get lesson progress ordered by date
        lesson_progress = LessonProgress.query.filter_by(
            student_id=user_id
        ).order_by(desc(LessonProgress.viewed_at)).all()
        
        if not lesson_progress:
            return jsonify({
                'current_streak': 0,
                'longest_streak': 0,
                'last_activity': None
            }), 200
        
        # Calculate current streak
        current_streak = 0
        last_date = None
        dates_with_activity = set()
        
        for progress in lesson_progress:
            if progress.viewed_at:
                date = progress.viewed_at.date()
                dates_with_activity.add(date)
        
        # Sort dates
        sorted_dates = sorted(dates_with_activity, reverse=True)
        
        if sorted_dates:
            # Check if studied today or yesterday
            today = datetime.utcnow().date()
            if sorted_dates[0] == today or sorted_dates[0] == today - timedelta(days=1):
                current_streak = 1
                last_date = sorted_dates[0]
                
                # Count consecutive days
                for i in range(1, len(sorted_dates)):
                    if (last_date - sorted_dates[i]).days == 1:
                        current_streak += 1
                        last_date = sorted_dates[i]
                    else:
                        break
        
        # Calculate longest streak
        longest_streak = 0
        temp_streak = 1
        
        for i in range(1, len(sorted_dates)):
            if (sorted_dates[i-1] - sorted_dates[i]).days == 1:
                temp_streak += 1
            else:
                longest_streak = max(longest_streak, temp_streak)
                temp_streak = 1
        
        longest_streak = max(longest_streak, temp_streak)
        
        return jsonify({
            'current_streak': current_streak,
            'longest_streak': longest_streak,
            'last_activity': sorted_dates[0].isoformat() if sorted_dates else None,
            'total_study_days': len(dates_with_activity)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/recommendations', methods=['GET'])
@student_required()
def get_course_recommendations():
    """Get course recommendations for student"""
    try:
        user_id = get_jwt_identity()
        
        # Get student's enrolled courses and categories
        enrolled_courses = db.session.query(Enrollment.course_id).filter_by(
            student_id=user_id
        ).subquery()
        
        from app.models import Course
        student_categories = db.session.query(
            func.distinct(Course.category)
        ).join(enrolled_courses, Course.id == enrolled_courses.c.course_id).all()
        
        student_categories = [cat[0] for cat in student_categories if cat[0]]
        
        # Get recommended courses
        recommendations_query = Course.query.filter(
            Course.is_published == True,
            ~Course.id.in_(db.session.query(enrolled_courses.c.course_id))
        )
        
        # Prioritize courses in same categories
        if student_categories:
            recommendations_query = recommendations_query.filter(
                Course.category.in_(student_categories)
            )
        
        recommendations = recommendations_query.limit(5).all()
        
        # If not enough recommendations, add popular courses
        if len(recommendations) < 5:
            popular_courses = Course.query.filter(
                Course.is_published == True,
                ~Course.id.in_(db.session.query(enrolled_courses.c.course_id)),
                ~Course.id.in_([r.id for r in recommendations])
            ).join(Enrollment).group_by(Course.id).order_by(
                desc(func.count(Enrollment.id))
            ).limit(5 - len(recommendations)).all()
            
            recommendations.extend(popular_courses)
        
        recommendations_data = []
        for course in recommendations:
            course_data = course.to_dict()
            course_data['recommendation_reason'] = f"Based on your interest in {course.category}" if course.category in student_categories else "Popular course"
            recommendations_data.append(course_data)
        
        return jsonify({
            'recommendations': recommendations_data,
            'total': len(recommendations_data)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500