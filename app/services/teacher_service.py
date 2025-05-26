from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy import desc, func
from app.models import db, User, Course, Enrollment, Lesson, Quiz, Assignment, QuizAttempt, AssignmentSubmission, LessonProgress
from app.utils.base_controller import ValidationException, PermissionException, NotFoundException
from app.utils.helpers import calculate_course_statistics, calculate_quiz_statistics
from collections import defaultdict
import io
import csv
from flask import make_response, jsonify

class TeacherService:
    """Service for teacher-specific operations"""
    
    @staticmethod
    def get_dashboard(teacher_id: int) -> Dict[str, Any]:
        """Get teacher dashboard data"""
        user = User.query.get(teacher_id)
        if not user or not user.is_teacher():
            raise PermissionException("Only teachers can access this dashboard")
        
        courses = user.taught_courses.all()
        
        total_courses = len(courses)
        published_courses = len([c for c in courses if c.is_published])
        
        total_students = 0
        active_students = 0
        for course in courses:
            enrollments = course.enrollments.all()
            total_students += len(enrollments)
            active_students += len([e for e in enrollments if e.status == 'active'])
        
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_enrollments = 0
        recent_submissions = 0
        
        for course in courses:
            recent_enrollments += course.enrollments.filter(
                Enrollment.enrolled_at >= week_ago
            ).count()
            
            for assignment in course.assignments:
                recent_submissions += assignment.submissions.filter(
                    AssignmentSubmission.submitted_at >= week_ago
                ).count()
        
        course_performance = []
        for course in courses[:5]:  
            stats = calculate_course_statistics(course)
            course_performance.append({
                'id': course.id,
                'title': course.title,
                'students': stats['total_students'],
                'completion_rate': stats['completion_rate'],
                'lessons': stats['total_lessons'],
                'quizzes': stats['total_quizzes']
            })
        
        recent_quiz_attempts = []
        for course in courses:
            for quiz in course.quizzes:
                attempts = quiz.attempts.filter(
                    QuizAttempt.submitted_at >= week_ago
                ).order_by(desc(QuizAttempt.submitted_at)).limit(5).all()
                
                for attempt in attempts:
                    recent_quiz_attempts.append({
                        'student_name': attempt.student.full_name,
                        'quiz_title': quiz.title,
                        'course_title': course.title,
                        'score': attempt.score,
                        'submitted_at': attempt.submitted_at.isoformat() if attempt.submitted_at else None
                    })
        
        recent_quiz_attempts.sort(key=lambda x: x['submitted_at'], reverse=True)
        recent_quiz_attempts = recent_quiz_attempts[:10]
        
        return {
            'stats': {
                'total_courses': total_courses,
                'published_courses': published_courses,
                'total_students': total_students,
                'active_students': active_students,
                'recent_enrollments': recent_enrollments,
                'recent_submissions': recent_submissions
            },
            'top_courses': course_performance,
            'recent_quiz_attempts': recent_quiz_attempts
        }
    
    @staticmethod
    def get_teacher_courses(teacher_id: int, page: int = 1, per_page: int = 12) -> Dict[str, Any]:
        """Get all courses for a teacher with pagination"""
        user = User.query.get(teacher_id)
        if not user or not user.is_teacher():
            raise PermissionException("Only teachers can access their courses")
        
        query = user.taught_courses.order_by(desc(Course.created_at))
        
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
    def get_course_details(teacher_id: int, course_id: int) -> Dict[str, Any]:
        """Get detailed course information for teacher"""
        user = User.query.get(teacher_id)
        if not user or not user.is_teacher():
            raise PermissionException("Only teachers can access course details")
        
        course = Course.query.get(course_id)
        if not course:
            raise NotFoundException("Course not found")
        
        if course.teacher_id != teacher_id:
            raise PermissionException("Access denied to this course")
        
        course_data = course.to_dict()
        course_data['statistics'] = calculate_course_statistics(course)
        
        lessons = course.lessons.order_by(Lesson.order_number).all()
        course_data['lessons'] = [lesson.to_dict() for lesson in lessons]
        
        quizzes = course.quizzes.all()
        course_data['quizzes'] = [quiz.to_dict() for quiz in quizzes]
        
        assignments = course.assignments.all()
        course_data['assignments'] = [assignment.to_dict() for assignment in assignments]
        
        enrollments = course.enrollments.filter_by(status='active').all()
        students = []
        for enrollment in enrollments:
            student_data = enrollment.student.to_dict()
            student_data['enrollment'] = enrollment.to_dict()
            student_data['progress'] = TeacherService._calculate_student_progress(
                enrollment.student_id, course_id
            )
            students.append(student_data)
        
        course_data['students'] = students
        
        return course_data
    
    @staticmethod
    def get_pending_submissions(teacher_id: int) -> Dict[str, Any]:
        """Get assignments that need grading"""
        user = User.query.get(teacher_id)
        if not user or not user.is_teacher():
            raise PermissionException("Only teachers can access submissions")
        
        courses = user.taught_courses.all()
        
        pending_submissions = []
        for course in courses:
            for assignment in course.assignments:
                submissions = assignment.submissions.filter_by(status='submitted').all()
                
                for submission in submissions:
                    submission_data = submission.to_dict()
                    submission_data['student'] = submission.student.to_dict()
                    submission_data['assignment'] = assignment.to_dict()
                    submission_data['course'] = course.to_dict()
                    pending_submissions.append(submission_data)
        
        pending_submissions.sort(key=lambda x: x['submitted_at'], reverse=True)
        
        return {
            'submissions': pending_submissions,
            'total': len(pending_submissions)
        }
    
    @staticmethod
    def get_quiz_analytics(teacher_id: int, quiz_id: int) -> Dict[str, Any]:
        """Get detailed quiz analytics"""
        user = User.query.get(teacher_id)
        if not user or not user.is_teacher():
            raise PermissionException("Only teachers can access quiz analytics")
        
        quiz = Quiz.query.get(quiz_id)
        if not quiz:
            raise NotFoundException("Quiz not found")
        
        if quiz.course.teacher_id != teacher_id:
            raise PermissionException("Access denied to this quiz")
        
        attempts = quiz.attempts.filter_by(status='completed').all()
        
        stats = calculate_quiz_statistics(attempts)
        
        question_analytics = []
        for question in quiz.questions:
            correct_count = 0
            total_answers = 0
            answer_distribution = {}
            
            for attempt in attempts:
                student_answer = next(
                    (sa for sa in attempt.student_answers if sa.question_id == question.id),
                    None
                )
                
                if student_answer:
                    total_answers += 1
                    if student_answer.is_correct:
                        correct_count += 1
                    
                    if question.question_type in ['multiple_choice', 'true_false']:
                        option_id = student_answer.selected_option_id
                        if option_id:
                            option_text = student_answer.selected_option.option_text
                            answer_distribution[option_text] = answer_distribution.get(option_text, 0) + 1
            
            question_analytics.append({
                'question': question.to_dict(),
                'total_answers': total_answers,
                'correct_answers': correct_count,
                'accuracy_rate': (correct_count / total_answers * 100) if total_answers > 0 else 0,
                'answer_distribution': answer_distribution
            })
        
        student_performance = []
        for attempt in attempts:
            student_performance.append({
                'student': attempt.student.to_dict(),
                'attempt': attempt.to_dict()
            })
        
        student_performance.sort(key=lambda x: x['attempt']['score'], reverse=True)
        
        return {
            'quiz': quiz.to_dict(),
            'statistics': stats,
            'question_analytics': question_analytics,
            'student_performance': student_performance
        }
    
    @staticmethod
    def get_student_progress_report(teacher_id: int, course_id: int) -> Dict[str, Any]:
        """Get detailed student progress report for a course"""
        user = User.query.get(teacher_id)
        if not user or not user.is_teacher():
            raise PermissionException("Only teachers can access student progress")
        
        course = Course.query.get(course_id)
        if not course:
            raise NotFoundException("Course not found")
        
        if course.teacher_id != teacher_id:
            raise PermissionException("Access denied to this course")
        
        enrollments = course.enrollments.filter_by(status='active').all()
        
        student_reports = []
        for enrollment in enrollments:
            student = enrollment.student
            progress = TeacherService._calculate_student_progress(student.id, course_id)
            
            recent_lessons = LessonProgress.query.filter_by(
                student_id=student.id
            ).join(Lesson).filter(
                Lesson.course_id == course_id,
                LessonProgress.viewed_at >= datetime.utcnow() - timedelta(days=7)
            ).count()
            
            recent_quiz_attempts = QuizAttempt.query.filter_by(
                student_id=student.id
            ).join(Quiz).filter(
                Quiz.course_id == course_id,
                QuizAttempt.started_at >= datetime.utcnow() - timedelta(days=7)
            ).count()
            
            student_reports.append({
                'student': student.to_dict(),
                'enrollment': enrollment.to_dict(),
                'progress': progress,
                'recent_activity': {
                    'lessons_viewed': recent_lessons,
                    'quiz_attempts': recent_quiz_attempts
                }
            })
        
        student_reports.sort(key=lambda x: x['progress']['overall_percentage'], reverse=True)
        
        return {
            'course': course.to_dict(),
            'student_reports': student_reports,
            'total_students': len(student_reports)
        }
    
    @staticmethod
    def get_course_analytics(teacher_id: int, course_id: int) -> Dict[str, Any]:
        """Get comprehensive course analytics"""
        user = User.query.get(teacher_id)
        if not user or not user.is_teacher():
            raise PermissionException("Only teachers can access course analytics")
        
        course = Course.query.get(course_id)
        if not course:
            raise NotFoundException("Course not found")
        
        if course.teacher_id != teacher_id:
            raise PermissionException("Access denied to this course")
        
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        enrollment_data = []
        
        for i in range(30):
            date = thirty_days_ago + timedelta(days=i)
            count = course.enrollments.filter(
                func.date(Enrollment.enrolled_at) == date.date()
            ).count()
            enrollment_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'enrollments': count
            })
        
        lesson_engagement = []
        for lesson in course.lessons:
            views = LessonProgress.query.filter_by(lesson_id=lesson.id).count()
            completions = LessonProgress.query.filter_by(
                lesson_id=lesson.id
            ).filter(LessonProgress.completed_at.isnot(None)).count()
            
            lesson_engagement.append({
                'lesson': lesson.to_dict(),
                'views': views,
                'completions': completions,
                'completion_rate': (completions / views * 100) if views > 0 else 0
            })
        
        quiz_performance = []
        for quiz in course.quizzes:
            attempts = quiz.attempts.filter_by(status='completed').all()
            if attempts:
                avg_score = sum(a.score for a in attempts if a.score) / len(attempts)
                quiz_performance.append({
                    'quiz': quiz.to_dict(),
                    'total_attempts': len(attempts),
                    'average_score': avg_score,
                    'pass_rate': len([a for a in attempts if a.score >= quiz.passing_score]) / len(attempts) * 100
                })
        
        return {
            'course': course.to_dict(),
            'enrollment_trends': enrollment_data,
            'lesson_engagement': lesson_engagement,
            'quiz_performance': quiz_performance,
            'overall_stats': calculate_course_statistics(course)
        }
    
    @staticmethod
    def _calculate_student_progress(student_id: int, course_id: int) -> Dict[str, Any]:
        """Calculate comprehensive student progress for a course"""
        course = Course.query.get(course_id)
        
        total_lessons = course.lessons.count()
        completed_lessons = LessonProgress.query.filter_by(
            student_id=student_id
        ).join(Lesson).filter(
            Lesson.course_id == course_id,
            LessonProgress.completed_at.isnot(None)
        ).count()
        
        quiz_scores = []
        for quiz in course.quizzes:
            best_attempt = QuizAttempt.query.filter_by(
                student_id=student_id,
                quiz_id=quiz.id,
                status='completed'
            ).order_by(desc(QuizAttempt.score)).first()
            
            if best_attempt:
                quiz_scores.append({
                    'quiz_id': quiz.id,
                    'quiz_title': quiz.title,
                    'score': best_attempt.score,
                    'passed': best_attempt.score >= quiz.passing_score
                })
        
        assignment_grades = []
        for assignment in course.assignments:
            submission = AssignmentSubmission.query.filter_by(
                student_id=student_id,
                assignment_id=assignment.id
            ).first()
            
            if submission:
                assignment_grades.append({
                    'assignment_id': assignment.id,
                    'assignment_title': assignment.title,
                    'grade': submission.grade,
                    'status': submission.status
                })
        
        lesson_progress = (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0
        quiz_average = sum(q['score'] for q in quiz_scores) / len(quiz_scores) if quiz_scores else 0
        assignment_average = sum(a['grade'] for a in assignment_grades if a['grade']) / len([a for a in assignment_grades if a['grade']]) if assignment_grades else 0
        
        overall_percentage = (lesson_progress + quiz_average + assignment_average) / 3
        
        return {
            'lessons': {
                'completed': completed_lessons,
                'total': total_lessons,
                'percentage': lesson_progress
            },
            'quizzes': quiz_scores,
            'assignments': assignment_grades,
            'quiz_average': quiz_average,
            'assignment_average': assignment_average,
            'overall_percentage': overall_percentage
        }
    
   
    @staticmethod
    def get_teacher_analytics_overview(teacher_id: int) -> Dict[str, Any]:
        """Aggregate analytics overview across all courses taught by the teacher"""
        user = User.query.get(teacher_id)
        if not user or not user.is_teacher():
            raise PermissionException("Only teachers can access this analytics overview")

        courses = user.taught_courses.all()

        total_students = 0
        total_completion = 0
        total_days = 0
        completion_counts = 0
        lesson_engagement = []
        quiz_performance = []

        enrollment_trends_counter = defaultdict(int)
        start_date = datetime.utcnow() - timedelta(days=30)

        for course in courses:
            stats = TeacherService.get_course_analytics(teacher_id, course.id)

            total_students += stats["overall_stats"].get("total_students", 0)
            total_completion += stats["overall_stats"].get("completion_rate", 0)
            total_days += stats["overall_stats"].get("average_completion_days", 0)
            completion_counts += 1

            lesson_engagement += stats.get("lesson_engagement", [])
            quiz_performance += stats.get("quiz_performance", [])

            enrollments = course.enrollments.filter(
                Enrollment.enrolled_at >= start_date
            ).all()
            for e in enrollments:
                day = e.enrolled_at.date().isoformat()
                enrollment_trends_counter[day] += 1

        enrollment_trends = []
        for i in range(30):
            date = (start_date + timedelta(days=i)).date().isoformat()
            enrollment_trends.append({
                "date": date,
                "enrollments": enrollment_trends_counter.get(date, 0)
            })

        return {
            "summary": {
                "total_courses": len(courses),
                "total_students": total_students,
                "avg_completion_rate": round(total_completion / completion_counts, 1) if completion_counts else 0,
                "avg_completion_days": round(total_days / completion_counts, 1) if completion_counts else 0
            },
            "enrollment_trends": enrollment_trends,
            "lesson_engagement": lesson_engagement,
            "quiz_performance": quiz_performance
        }

    @staticmethod
    def get_individual_student_progress(teacher_id: int, student_id: int, course_id: int) -> Dict[str, Any]:
        user = User.query.get(teacher_id)
        if not user or not user.is_teacher():
            raise PermissionException("Only teachers can access this data")

        course = Course.query.get(course_id)
        if not course or course.teacher_id != teacher_id:
            raise PermissionException("Access denied to this course")

        student = User.query.get(student_id)
        if not student:
            raise NotFoundException("Student not found")

        progress = TeacherService._calculate_student_progress(student_id, course_id)

        return {
            'student': student.to_dict(),
            'course': course.to_dict(),
            'progress': progress
        }

    @staticmethod
    def export_course_students(teacher_id: int, course_id: int):
        """Export course students to CSV"""
        user = User.query.get(teacher_id)
        if not user or not user.is_teacher():
            raise PermissionException("Only teachers can export student data")
        
        course = Course.query.get(course_id)
        if not course:
            raise NotFoundException("Course not found")
        
        if course.teacher_id != teacher_id:
            raise PermissionException("Access denied to this course")
        
        report_data = TeacherService.get_student_progress_report(teacher_id, course_id)
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'Student Name', 'Email', 'Enrollment Date', 'Progress %', 
            'Lessons Completed', 'Quiz Average', 'Assignment Average',
            'Last Activity', 'Status'
        ])
        
        for report in report_data['student_reports']:
            student = report['student']
            enrollment = report['enrollment']
            progress = report['progress']
            
            last_activity = 'Never'
            if enrollment.get('enrolled_at'):
                try:
                    from datetime import datetime
                    enrollment_date = enrollment['enrolled_at']
                    if isinstance(enrollment_date, str):
                        last_activity = enrollment_date[:10]
                    else:
                        last_activity = enrollment_date.strftime('%Y-%m-%d')
                except (TypeError, AttributeError):
                    last_activity = 'Never'
            
            lessons = progress.get('lessons', {})
            completed_lessons = lessons.get('completed', 0)
            total_lessons = lessons.get('total', 0)
            
            writer.writerow([
                student.get('full_name', 'Unknown'),
                student.get('email', ''),
                enrollment.get('enrolled_at', '')[:10] if enrollment.get('enrolled_at') else '',
                f"{progress.get('overall_percentage', 0):.1f}",
                f"{completed_lessons}/{total_lessons}",
                f"{progress.get('quiz_average', 0):.1f}",
                f"{progress.get('assignment_average', 0):.1f}",
                last_activity,
                enrollment.get('status', 'unknown')
            ])
        
        output.seek(0)
        csv_content = output.getvalue()
        output.close()
        
        return csv_content
    
    @staticmethod
    def get_all_submissions(teacher_id: int) -> Dict[str, Any]:
        """Get all submissions (not just pending)"""
        user = User.query.get(teacher_id)
        if not user or not user.is_teacher():
            raise PermissionException("Only teachers can access submissions")

        courses = user.taught_courses.all()
        all_submissions = []

        for course in courses:
            for assignment in course.assignments:
                submissions = assignment.submissions.all() 
                for submission in submissions:
                    submission_data = submission.to_dict()
                    submission_data['student'] = submission.student.to_dict()
                    submission_data['assignment'] = assignment.to_dict()
                    submission_data['course'] = course.to_dict()
                    all_submissions.append(submission_data)

        all_submissions.sort(key=lambda x: x['submitted_at'], reverse=True)

        return {
            'submissions': all_submissions,
            'total': len(all_submissions)
        }

