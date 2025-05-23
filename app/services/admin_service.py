from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy import func, desc, or_
from app.models import db, User, Course, Enrollment, Quiz, QuizAttempt, Assignment, Achievement
from app.utils.base_controller import ValidationException, PermissionException, NotFoundException
from app.utils.helpers import calculate_course_statistics
import csv
import io

class AdminService:
    """Service for admin-specific operations"""
    
    @staticmethod
    def get_dashboard() -> Dict[str, Any]:
        """Get admin dashboard statistics"""
        try:
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
        except Exception as e:
            print(f"Error in get_dashboard: {str(e)}")
            return {
                'users': {'total': 0, 'students': 0, 'teachers': 0, 'active': 0, 'recent': 0},
                'courses': {'total': 0, 'published': 0, 'recent': 0},
                'enrollments': {'total': 0, 'active': 0, 'completed': 0, 'recent': 0},
                'quizzes': {'total': 0, 'attempts': 0}
            }
    
    @staticmethod
    def get_users(page: int = 1, per_page: int = 20, role: Optional[str] = None,
                  status: Optional[str] = None, search: Optional[str] = None) -> Dict[str, Any]:
        """Get all users with filtering and pagination - FIXED FILTERS"""
        try:
            query = User.query
            
            # Apply role filter
            if role and role.strip():
                print(f"Applying role filter: {role}")
                query = query.filter_by(role=role.strip())
            
            # Apply status filter - FIXED!
            if status and status.strip():
                print(f"Applying status filter: {status}")
                if status.strip().lower() == 'active':
                    query = query.filter_by(is_active=True)
                elif status.strip().lower() == 'inactive':
                    query = query.filter_by(is_active=False)
            
            # Apply search filter
            if search and search.strip():
                print(f"Applying search filter: {search}")
                search_term = f"%{search.strip()}%"
                query = query.filter(
                    or_(
                        User.username.like(search_term),
                        User.email.like(search_term),
                        User.full_name.like(search_term)
                    )
                )
            
            # Order by creation date
            query = query.order_by(desc(User.created_at))
            
            # Get total count before pagination
            total = query.count()
            print(f"Total users found: {total}")
            
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
        except Exception as e:
            print(f"Error in get_users: {str(e)}")
            return {
                'users': [],
                'total': 0,
                'page': 1,
                'per_page': per_page,
                'pages': 1
            }
    
    @staticmethod
    def get_user(user_id: int) -> Dict[str, Any]:
        """Get detailed user information"""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundException("User not found")
        
        user_data = user.to_dict()
        
        try:
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
            else:  # admin
                user_data['detailed_stats'] = {
                    'total_users_managed': User.query.count(),
                    'total_courses_managed': Course.query.count(),
                    'admin_since': user.created_at.isoformat() if user.created_at else None
                }
        except Exception as e:
            print(f"Error calculating user stats: {str(e)}")
            user_data['detailed_stats'] = {}
        
        return user_data
    
    @staticmethod
    def update_user(admin_id: int, user_id: int, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user information"""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundException("User not found")
        
        # Don't allow editing other admins unless you're the same admin
        if user.is_admin() and user.id != admin_id:
            raise PermissionException("Cannot edit other admin users")
        
        # Update allowed fields
        allowed_fields = ['full_name', 'email', 'phone', 'age', 'is_active']
        
        for field in allowed_fields:
            if field in user_data:
                if field == 'email':
                    # Check if email is already taken by another user
                    existing_user = User.query.filter_by(email=user_data['email']).first()
                    if existing_user and existing_user.id != user_id:
                        raise ValidationException('Email already taken by another user')
                
                if field == 'age' and user_data[field]:
                    try:
                        age = int(user_data[field])
                        if age < 13 or age > 120:
                            raise ValidationException('Age must be between 13 and 120')
                        user_data[field] = age
                    except ValueError:
                        raise ValidationException('Age must be a valid number')
                
                setattr(user, field, user_data[field])
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return {
            'message': 'User updated successfully',
            'user': user.to_dict()
        }
    
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
    def export_users(role: Optional[str] = None, status: Optional[str] = None, 
                    search: Optional[str] = None) -> Dict[str, Any]:
        """Export users to CSV format"""
        try:
            query = User.query
            
            # Apply same filters as get_users
            if role and role.strip():
                query = query.filter_by(role=role.strip())
            
            if status and status.strip():
                if status.strip().lower() == 'active':
                    query = query.filter_by(is_active=True)
                elif status.strip().lower() == 'inactive':
                    query = query.filter_by(is_active=False)
            
            if search and search.strip():
                search_term = f"%{search.strip()}%"
                query = query.filter(
                    or_(
                        User.username.like(search_term),
                        User.email.like(search_term),
                        User.full_name.like(search_term)
                    )
                )
            
            users = query.order_by(desc(User.created_at)).all()
            
            # Create CSV content
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                'ID', 'Username', 'Email', 'Full Name', 'Role', 
                'Phone', 'Age', 'Active', 'Created At', 'Updated At'
            ])
            
            # Write user data
            for user in users:
                writer.writerow([
                    user.id,
                    user.username,
                    user.email,
                    user.full_name,
                    user.role.value,
                    user.phone or '',
                    user.age or '',
                    'Yes' if user.is_active else 'No',
                    user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else '',
                    user.updated_at.strftime('%Y-%m-%d %H:%M:%S') if user.updated_at else ''
                ])
            
            csv_content = output.getvalue()
            output.close()
            
            filename = f"users_{datetime.utcnow().strftime('%Y%m%d')}.csv"
            
            return {
                'csv_content': csv_content,
                'filename': filename,
                'total_exported': len(users)
            }
            
        except Exception as e:
            print(f"Error in export_users: {str(e)}")
            raise ValidationException(f"Export failed: {str(e)}")
    
    @staticmethod
    def get_all_courses(page: int = 1, per_page: int = 20, category: Optional[str] = None,
                       status: Optional[str] = None, search: Optional[str] = None) -> Dict[str, Any]:
        """Get all courses with detailed information - FIXED FILTERS"""
        try:
            query = Course.query
            
            # Apply category filter
            if category and category.strip():
                print(f"Applying category filter: {category}")
                query = query.filter_by(category=category.strip())
            
            # Apply status filter - FIXED!
            if status and status.strip():
                print(f"Applying status filter: {status}")
                if status.strip().lower() == 'published':
                    query = query.filter_by(is_published=True)
                elif status.strip().lower() == 'draft':
                    query = query.filter_by(is_published=False)
            
            # Apply search filter
            if search and search.strip():
                print(f"Applying search filter: {search}")
                search_term = f"%{search.strip()}%"
                query = query.filter(
                    or_(
                        Course.title.like(search_term),
                        Course.description.like(search_term)
                    )
                )
            
            # Order by creation date
            query = query.order_by(desc(Course.created_at))
            
            # Get total count before pagination
            total = query.count()
            print(f"Total courses found: {total}")
            
            pagination = query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            courses = []
            for course in pagination.items:
                course_data = course.to_dict()
                try:
                    course_data['statistics'] = calculate_course_statistics(course)
                except Exception as e:
                    print(f"Error calculating course statistics for course {course.id}: {str(e)}")
                    course_data['statistics'] = {
                        'total_students': 0,
                        'completion_rate': 0,
                        'total_lessons': 0,
                        'total_quizzes': 0,
                        'total_assignments': 0
                    }
                courses.append(course_data)
            
            return {
                'courses': courses,
                'total': pagination.total,
                'page': page,
                'per_page': per_page,
                'pages': pagination.pages
            }
        except Exception as e:
            print(f"Error in get_all_courses: {str(e)}")
            return {
                'courses': [],
                'total': 0,
                'page': 1,
                'per_page': per_page,
                'pages': 1
            }
    
    
    @staticmethod
    def export_courses(category: Optional[str] = None, status: Optional[str] = None, 
                      search: Optional[str] = None) -> Dict[str, Any]:
        """Export courses to CSV format"""
        try:
            query = Course.query
            
            # Apply same filters as get_all_courses
            if category and category.strip():
                query = query.filter_by(category=category.strip())
            
            if status and status.strip():
                if status.strip().lower() == 'published':
                    query = query.filter_by(is_published=True)
                elif status.strip().lower() == 'draft':
                    query = query.filter_by(is_published=False)
            
            if search and search.strip():
                search_term = f"%{search.strip()}%"
                query = query.filter(
                    or_(
                        Course.title.like(search_term),
                        Course.description.like(search_term)
                    )
                )
            
            courses = query.order_by(desc(Course.created_at)).all()
            
            # Create CSV content
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                'ID', 'Title', 'Description', 'Category', 'Teacher', 
                'Students', 'Lessons', 'Quizzes', 'Assignments', 'Status', 'Created At'
            ])
            
            # Write course data
            for course in courses:
                try:
                    stats = calculate_course_statistics(course)
                except:
                    stats = {'total_students': 0, 'total_lessons': 0, 'total_quizzes': 0, 'total_assignments': 0}
                
                writer.writerow([
                    course.id,
                    course.title,
                    course.description[:100] + '...' if course.description and len(course.description) > 100 else course.description or '',
                    course.category or '',
                    course.teacher.full_name if course.teacher else '',
                    stats.get('total_students', 0),
                    stats.get('total_lessons', 0),
                    stats.get('total_quizzes', 0),
                    stats.get('total_assignments', 0),
                    'Published' if course.is_published else 'Draft',
                    course.created_at.strftime('%Y-%m-%d %H:%M:%S') if course.created_at else ''
                ])
            
            csv_content = output.getvalue()
            output.close()
            
            timestamp = datetime.utcnow().strftime('%Y%m%d')
            filename = f"courses_{timestamp}.csv"
            
            return {
                'csv_content': csv_content,
                'filename': filename,
                'total_exported': len(courses)
            }
            
        except Exception as e:
            print(f"Error in export_courses: {str(e)}")
            raise ValidationException(f"Export failed: {str(e)}")
    
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
        """Get user activity report with better data formatting"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Create a complete date range for the period
            date_range = []
            current_date = start_date.date()
            end_date = datetime.utcnow().date()
            
            while current_date <= end_date:
                date_range.append(current_date)
                current_date += timedelta(days=1)
            
            # User registrations over time
            user_reg_data = db.session.query(
                func.date(User.created_at).label('date'),
                func.count(User.id).label('count')
            ).filter(
                User.created_at >= start_date
            ).group_by(
                func.date(User.created_at)
            ).all()
            
            # Course enrollments over time
            enrollment_data = db.session.query(
                func.date(Enrollment.enrolled_at).label('date'),
                func.count(Enrollment.id).label('count')
            ).filter(
                Enrollment.enrolled_at >= start_date
            ).group_by(
                func.date(Enrollment.enrolled_at)
            ).all()
            
            # Quiz attempts over time
            quiz_data = db.session.query(
                func.date(QuizAttempt.started_at).label('date'),
                func.count(QuizAttempt.id).label('count')
            ).filter(
                QuizAttempt.started_at >= start_date
            ).group_by(
                func.date(QuizAttempt.started_at)
            ).all()
            
            # Convert to dictionaries for easier lookup
            user_reg_dict = {item.date: item.count for item in user_reg_data}
            enrollment_dict = {item.date: item.count for item in enrollment_data}
            quiz_dict = {item.date: item.count for item in quiz_data}
            
            # Fill in missing dates with 0 counts
            user_registrations = []
            course_enrollments = []
            quiz_attempts = []
            
            for date in date_range:
                user_registrations.append({
                    'date': date.isoformat(),
                    'count': user_reg_dict.get(date, 0)
                })
                course_enrollments.append({
                    'date': date.isoformat(),
                    'count': enrollment_dict.get(date, 0)
                })
                quiz_attempts.append({
                    'date': date.isoformat(),
                    'count': quiz_dict.get(date, 0)
                })
            
            return {
                'period_days': days,
                'user_registrations': user_registrations,
                'course_enrollments': course_enrollments,
                'quiz_attempts': quiz_attempts
            }
        except Exception as e:
            print(f"Error in get_user_activity_report: {str(e)}")
            return {
                'period_days': days,
                'user_registrations': [],
                'course_enrollments': [],
                'quiz_attempts': []
            }

    @staticmethod
    def get_course_performance_report() -> Dict[str, Any]:
        """Get enhanced course performance report"""
        try:
            courses = Course.query.filter_by(is_published=True).all()
            
            course_performance = []
            for course in courses:
                try:
                    # Get enrollment statistics
                    total_enrollments = course.enrollments.count()
                    active_enrollments = course.enrollments.filter_by(status='active').count()
                    completed_enrollments = course.enrollments.filter_by(status='completed').count()
                    
                    # Calculate completion rate
                    completion_rate = 0
                    if total_enrollments > 0:
                        completion_rate = (completed_enrollments / total_enrollments) * 100
                    
                    # Get average quiz scores for the course
                    avg_quiz_score = db.session.query(
                        func.avg(QuizAttempt.score)
                    ).join(Quiz).filter(
                        Quiz.course_id == course.id,
                        QuizAttempt.status == 'completed'
                    ).scalar() or 0
                    
                    # Calculate average completion time
                    completed_enrollments_with_time = course.enrollments.filter(
                        Enrollment.status == 'completed',
                        Enrollment.enrolled_at.isnot(None),
                        Enrollment.completed_at.isnot(None)
                    ).all()
                    
                    avg_completion_days = 0
                    if completed_enrollments_with_time:
                        total_days = sum([
                            (enrollment.completed_at - enrollment.enrolled_at).days
                            for enrollment in completed_enrollments_with_time
                        ])
                        avg_completion_days = total_days / len(completed_enrollments_with_time)
                    
                    # Get content counts
                    total_lessons = course.lessons.count()
                    total_quizzes = course.quizzes.count()
                    total_assignments = course.assignments.count()
                    
                    course_performance.append({
                        'course_id': course.id,
                        'course_title': course.title,
                        'teacher_name': course.teacher.full_name if course.teacher else 'Unknown',
                        'category': course.category or 'General',
                        'total_students': total_enrollments,
                        'active_students': active_enrollments,
                        'completed_students': completed_enrollments,
                        'completion_rate': round(float(completion_rate), 2),
                        'average_quiz_score': round(float(avg_quiz_score), 2),
                        'total_lessons': total_lessons,
                        'total_quizzes': total_quizzes,
                        'total_assignments': total_assignments,
                        'average_completion_days': round(float(avg_completion_days), 1)
                    })
                except Exception as e:
                    print(f"Error processing course {course.id}: {str(e)}")
                    continue
            
            # Sort by completion rate (descending)
            course_performance.sort(key=lambda x: x['completion_rate'], reverse=True)
            
            return {
                'courses': course_performance,
                'total_courses': len(course_performance)
            }
        except Exception as e:
            print(f"Error in get_course_performance_report: {str(e)}")
            return {
                'courses': [],
                'total_courses': 0
            }

    @staticmethod
    def get_engagement_metrics() -> Dict[str, Any]:
        """Get student engagement metrics"""
        try:
            # Total active students
            active_students = User.query.filter_by(role='student', is_active=True).count()
            
            # Students with recent activity (last 7 days)
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_lesson_views = db.session.query(LessonProgress.student_id).filter(
                LessonProgress.viewed_at >= week_ago
            ).distinct().count()
            
            recent_quiz_attempts = db.session.query(QuizAttempt.student_id).filter(
                QuizAttempt.started_at >= week_ago
            ).distinct().count()
            
            # Average session time (simplified calculation)
            avg_lessons_per_student = db.session.query(
                func.avg(func.count(LessonProgress.id))
            ).filter(
                LessonProgress.viewed_at >= week_ago
            ).group_by(LessonProgress.student_id).scalar() or 0
            
            return {
                'active_students': active_students,
                'recent_lesson_viewers': recent_lesson_views,
                'recent_quiz_takers': recent_quiz_attempts,
                'avg_lessons_per_student': round(float(avg_lessons_per_student), 1),
                'engagement_rate': round((recent_lesson_views / active_students * 100), 1) if active_students > 0 else 0
            }
        except Exception as e:
            print(f"Error in get_engagement_metrics: {str(e)}")
            return {
                'active_students': 0,
                'recent_lesson_viewers': 0,
                'recent_quiz_takers': 0,
                'avg_lessons_per_student': 0,
                'engagement_rate': 0
            }

    @staticmethod
    def get_category_distribution() -> Dict[str, Any]:
        """Get course category distribution"""
        try:
            category_data = db.session.query(
                Course.category,
                func.count(Course.id).label('count')
            ).filter(
                Course.is_published == True
            ).group_by(Course.category).all()
            
            categories = []
            for item in category_data:
                categories.append({
                    'category': item.category or 'General',
                    'count': item.count
                })
            
            # Sort by count (descending)
            categories.sort(key=lambda x: x['count'], reverse=True)
            
            return {
                'categories': categories,
                'total_categories': len(categories)
            }
        except Exception as e:
            print(f"Error in get_category_distribution: {str(e)}")
            return {
                'categories': [],
                'total_categories': 0
            }

    @staticmethod
    def export_performance_report(format_type: str = 'csv') -> Dict[str, Any]:
        """Export performance report in specified format"""
        try:
            performance_data = AdminService.get_course_performance_report()
            
            if format_type.lower() == 'csv':
                # Create CSV content
                output = io.StringIO()
                writer = csv.writer(output)
                
                # Write header
                writer.writerow([
                    'Course ID', 'Course Title', 'Instructor', 'Category',
                    'Total Students', 'Active Students', 'Completed Students',
                    'Completion Rate (%)', 'Average Quiz Score (%)',
                    'Total Lessons', 'Total Quizzes', 'Total Assignments',
                    'Average Completion Days'
                ])
                
                # Write course data
                for course in performance_data['courses']:
                    writer.writerow([
                        course['course_id'],
                        course['course_title'],
                        course['teacher_name'],
                        course['category'],
                        course['total_students'],
                        course['active_students'],
                        course['completed_students'],
                        course['completion_rate'],
                        course['average_quiz_score'],
                        course['total_lessons'],
                        course['total_quizzes'],
                        course['total_assignments'],
                        course['average_completion_days']
                    ])
                
                csv_content = output.getvalue()
                output.close()
                
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                filename = f"course_performance_report_{timestamp}.csv"
                
                return {
                    'content': csv_content,
                    'filename': filename,
                    'content_type': 'text/csv',
                    'total_exported': len(performance_data['courses'])
                }
            
            else:
                raise ValidationException(f"Unsupported export format: {format_type}")
                
        except Exception as e:
            print(f"Error in export_performance_report: {str(e)}")
            raise ValidationException(f"Export failed: {str(e)}")
    
    @staticmethod
    def get_achievements() -> Dict[str, Any]:
        """Get all achievements"""
        try:
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
        except Exception as e:
            print(f"Error in get_achievements: {str(e)}")
            return {
                'achievements': [],
                'total': 0
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