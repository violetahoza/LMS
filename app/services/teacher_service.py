from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy import desc, func
from app.models import AnswerOption, Question, StudentAnswer, db, User, Course, Enrollment, Lesson, Quiz, Assignment, QuizAttempt, AssignmentSubmission, LessonProgress
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
        
        week_ago = datetime.now() - timedelta(days=7)
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
        """Get detailed quiz analytics with REAL student performance data"""
        user = User.query.get(teacher_id)
        if not user or not user.is_teacher():
            raise PermissionException("Only teachers can access quiz analytics")
        
        quiz = Quiz.query.get(quiz_id)
        if not quiz:
            raise NotFoundException("Quiz not found")
        
        if quiz.course.teacher_id != teacher_id:
            raise PermissionException("Access denied to this quiz")
        
        best_attempts = db.session.query(QuizAttempt).filter(
            QuizAttempt.quiz_id == quiz_id,
            QuizAttempt.status == 'completed',
            QuizAttempt.score.isnot(None)
        ).join(User, QuizAttempt.student_id == User.id).all()
        
        student_best_attempts = {}
        for attempt in best_attempts:
            student_id = attempt.student_id
            if student_id not in student_best_attempts or attempt.score > student_best_attempts[student_id].score:
                student_best_attempts[student_id] = attempt
        
        best_attempts = list(student_best_attempts.values())
        
        if best_attempts:
            scores = [attempt.score for attempt in best_attempts if attempt.score is not None]
            stats = {
                'total_attempts': len(best_attempts),
                'average_score': sum(scores) / len(scores) if scores else 0,
                'highest_score': max(scores) if scores else 0,
                'lowest_score': min(scores) if scores else 0,
                'pass_rate': len([s for s in scores if s >= quiz.passing_score]) / len(scores) * 100 if scores else 0
            }
        else:
            stats = {
                'total_attempts': 0,
                'average_score': 0,
                'highest_score': 0,
                'lowest_score': 0,
                'pass_rate': 0
            }
        
        question_analytics = []
        questions = quiz.questions.order_by(Question.order_number).all()
        
        for question in questions:
            student_answers = []
            for attempt in best_attempts:
                answer = db.session.query(StudentAnswer).filter(
                    StudentAnswer.attempt_id == attempt.id,
                    StudentAnswer.question_id == question.id
                ).first()
                if answer:
                    student_answers.append(answer)
            
            correct_count = len([ans for ans in student_answers if ans.is_correct == True])
            total_answers = len(student_answers)
            
            answer_distribution = {}
            if question.question_type in ['multiple_choice', 'true_false']:
                for answer in student_answers:
                    if answer.selected_option_id:
                        option = AnswerOption.query.get(answer.selected_option_id)
                        if option:
                            key = option.option_text
                            answer_distribution[key] = answer_distribution.get(key, 0) + 1
            elif question.question_type == 'short_answer':
                for answer in student_answers:
                    if answer.answer_text:
                        key = (answer.answer_text[:50] + "...") if len(answer.answer_text) > 50 else answer.answer_text
                        answer_distribution[key] = answer_distribution.get(key, 0) + 1
            
            question_analytics.append({
                'question': {
                    'id': question.id,
                    'question_text': question.question_text,
                    'question_type': question.question_type,
                    'points': question.points,
                    'order_number': question.order_number
                },
                'total_answers': total_answers,
                'correct_answers': correct_count,
                'accuracy_rate': (correct_count / total_answers * 100) if total_answers > 0 else 0,
                'answer_distribution': answer_distribution
            })
        
        student_performance = []
        for attempt in best_attempts:
            answers = db.session.query(StudentAnswer).filter(
                StudentAnswer.attempt_id == attempt.id
            ).join(Question).order_by(Question.order_number).all()
            
            question_breakdown = []
            for answer in answers:
                question = answer.question
                breakdown_item = {
                    'question_id': question.id,
                    'question_text': question.question_text[:100] + "..." if len(question.question_text) > 100 else question.question_text,
                    'question_type': question.question_type,
                    'points': question.points,
                    'points_earned': answer.points_earned or 0,
                    'is_correct': answer.is_correct,
                    'student_answer': None
                }
                
                if question.question_type == 'short_answer':
                    breakdown_item['student_answer'] = answer.answer_text
                elif answer.selected_option_id:
                    option = AnswerOption.query.get(answer.selected_option_id)
                    if option:
                        breakdown_item['student_answer'] = option.option_text
                
                question_breakdown.append(breakdown_item)
            
            student_performance.append({
                'student': {
                    'id': attempt.student.id,
                    'full_name': attempt.student.full_name,
                    'email': attempt.student.email,
                    'username': attempt.student.username
                },
                'attempt': {
                    'id': attempt.id,
                    'attempt_number': attempt.attempt_number,
                    'score': attempt.score,
                    'submitted_at': attempt.submitted_at.isoformat() if attempt.submitted_at else None,
                    'time_spent_minutes': attempt.time_spent_minutes,
                    'status': attempt.status,
                    'graded_at': attempt.graded_at.isoformat() if attempt.graded_at else None
                },
                'question_breakdown': question_breakdown
            })
        
        student_performance.sort(key=lambda x: x['attempt']['score'] or 0, reverse=True)
        
        return {
            'quiz': quiz.to_dict(),
            'statistics': stats,
            'question_statistics': question_analytics,
            'student_performance': student_performance,
            'total_students': len(student_performance)
    }
    
    @staticmethod
    def get_individual_student_progress(teacher_id: int, student_id: int, course_id: int) -> Dict[str, Any]:
        """Get REAL detailed progress for individual student"""
        user = User.query.get(teacher_id)
        if not user or not user.is_teacher():
            raise PermissionException("Only teachers can access this data")

        course = Course.query.get(course_id)
        if not course or course.teacher_id != teacher_id:
            raise PermissionException("Access denied to this course")

        student = User.query.get(student_id)
        if not student:
            raise NotFoundException("Student not found")

        enrollment = Enrollment.query.filter_by(
            student_id=student_id,
            course_id=course_id
        ).first()
        
        if not enrollment:
            raise NotFoundException("Student not enrolled in this course")

        progress = TeacherService._calculate_detailed_student_progress(student_id, course_id)
        
        last_activity = TeacherService._get_last_activity(student_id, course_id)
        
        return {
            'student': student.to_dict(),
            'course': course.to_dict(),
            'progress': {
                **progress,
                'overall_percentage': enrollment.calculate_progress(),  # Use the fixed calculation
                'last_activity': last_activity.isoformat() if last_activity else None,
                'time_spent_minutes': progress.get('total_time_spent', 0)
            }
        }
    
    @staticmethod
    def _calculate_detailed_student_progress(student_id: int, course_id: int) -> Dict[str, Any]:
        """Calculate REAL comprehensive student progress with actual database data"""
        course = Course.query.get(course_id)
        
        total_lessons = course.lessons.count()
        lesson_progress_records = db.session.query(LessonProgress).filter(
            LessonProgress.student_id == student_id
        ).join(Lesson).filter(
            Lesson.course_id == course_id
        ).all()
        
        completed_lessons = len([lp for lp in lesson_progress_records if lp.completed_at is not None])
        viewed_lessons = len(lesson_progress_records)
        total_lesson_time = sum([lp.time_spent_minutes or 0 for lp in lesson_progress_records])
        
        detailed_lessons = []
        for lesson in course.lessons.order_by(Lesson.order_number).all():
            progress_record = next((lp for lp in lesson_progress_records if lp.lesson_id == lesson.id), None)
            detailed_lessons.append({
                'lesson': lesson.to_dict(),
                'viewed': progress_record is not None,
                'completed': progress_record.completed_at is not None if progress_record else False,
                'time_spent': progress_record.time_spent_minutes or 0 if progress_record else 0,
                'last_viewed': progress_record.viewed_at.isoformat() if progress_record and progress_record.viewed_at else None
            })
        
        quiz_progress = []
        quiz_summary = {'total': 0, 'attempted': 0, 'passed': 0, 'average_score': 0}
        
        for quiz in course.quizzes.all():
            attempts = QuizAttempt.query.filter_by(
                student_id=student_id,
                quiz_id=quiz.id
            ).order_by(QuizAttempt.attempt_number).all()
            
            best_attempt = None
            if attempts:
                completed_attempts = [a for a in attempts if a.status == 'completed' and a.score is not None]
                if completed_attempts:
                    best_attempt = max(completed_attempts, key=lambda a: a.score)
            
            quiz_data = {
                'quiz_id': quiz.id,
                'quiz_title': quiz.title,
                'total_points': quiz.total_points,
                'passing_score': quiz.passing_score,
                'attempts': len(attempts),
                'max_attempts': quiz.max_attempts,
                'best_score': best_attempt.score if best_attempt else None,
                'passed': best_attempt.score >= quiz.passing_score if best_attempt else False,
                'last_attempt_date': best_attempt.submitted_at.isoformat() if best_attempt and best_attempt.submitted_at else None,
                'details': [{
                    'attempt_number': a.attempt_number,
                    'score': a.score,
                    'status': a.status,
                    'submitted_at': a.submitted_at.isoformat() if a.submitted_at else None,
                    'time_spent': a.time_spent_minutes
                } for a in attempts]
            }
            
            quiz_progress.append(quiz_data)
            quiz_summary['total'] += 1
            if attempts:
                quiz_summary['attempted'] += 1
                if quiz_data['passed']:
                    quiz_summary['passed'] += 1
        
        all_scores = [qp['best_score'] for qp in quiz_progress if qp['best_score'] is not None]
        quiz_summary['average_score'] = sum(all_scores) / len(all_scores) if all_scores else 0
        
        assignment_progress = []
        assignment_summary = {'total': 0, 'submitted': 0, 'graded': 0, 'average_score': 0}
        
        for assignment in course.assignments.all():
            submission = AssignmentSubmission.query.filter_by(
                student_id=student_id,
                assignment_id=assignment.id
            ).first()
            
            assignment_data = {
                'assignment_id': assignment.id,
                'assignment_title': assignment.title,
                'total_points': assignment.total_points,
                'due_date': assignment.due_date.isoformat() if assignment.due_date else None,
                'submitted': submission is not None,
                'submission_date': submission.submitted_at.isoformat() if submission and submission.submitted_at else None,
                'grade': submission.grade if submission else None,
                'status': submission.status if submission else 'not_submitted',
                'feedback': submission.feedback if submission else None,
                'graded_at': submission.graded_at.isoformat() if submission and submission.graded_at else None,
                'percentage': (submission.grade / assignment.total_points * 100) if submission and submission.grade is not None else None
            }
            
            assignment_progress.append(assignment_data)
            assignment_summary['total'] += 1
            if submission:
                assignment_summary['submitted'] += 1
                if submission.status == 'graded' and submission.grade is not None:
                    assignment_summary['graded'] += 1
        
        graded_assignments = [ap for ap in assignment_progress if ap['grade'] is not None]
        if graded_assignments:
            assignment_summary['average_score'] = sum([ap['percentage'] for ap in graded_assignments]) / len(graded_assignments)
        
        return {
            'lessons': {
                'completed': completed_lessons,
                'total': total_lessons,
                'viewed': viewed_lessons,
                'percentage': (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0
            },
            'quizzes': quiz_summary,
            'assignments': assignment_summary,
            'detailed_lessons': detailed_lessons,
            'detailed_quizzes': quiz_progress,
            'detailed_assignments': assignment_progress,
            'total_time_spent': total_lesson_time
        }
    
    @staticmethod
    def _get_last_activity(student_id: int, course_id: int) -> datetime:
        """Get the most recent activity timestamp for a student in a course"""
        activities = []
        
        latest_lesson = db.session.query(func.max(LessonProgress.viewed_at)).filter(
            LessonProgress.student_id == student_id
        ).join(Lesson).filter(Lesson.course_id == course_id).scalar()
        if latest_lesson:
            activities.append(latest_lesson)
        
        latest_quiz = db.session.query(func.max(QuizAttempt.submitted_at)).filter(
            QuizAttempt.student_id == student_id
        ).join(Quiz).filter(Quiz.course_id == course_id).scalar()
        if latest_quiz:
            activities.append(latest_quiz)
        
        latest_assignment = db.session.query(func.max(AssignmentSubmission.submitted_at)).filter(
            AssignmentSubmission.student_id == student_id
        ).join(Assignment).filter(Assignment.course_id == course_id).scalar()
        if latest_assignment:
            activities.append(latest_assignment)
        
        return max(activities) if activities else None
    
    @staticmethod
    def get_student_progress_report(teacher_id: int, course_id: int) -> Dict[str, Any]:
        """Get REAL detailed student progress report for a course"""
        user = User.query.get(teacher_id)
        if not user or not user.is_teacher():
            raise PermissionException("Only teachers can access student progress")
        
        course = Course.query.get(course_id)
        if not course:
            raise NotFoundException("Course not found")
        
        if course.teacher_id != teacher_id:
            raise PermissionException("Access denied to this course")
        
        enrollments = course.enrollments.filter(
            Enrollment.status.in_(['active', 'completed'])
        ).all()
        
        student_reports = []
        for enrollment in enrollments:
            student = enrollment.student
            
            progress = TeacherService._calculate_detailed_student_progress(student.id, course_id)
            
            current_progress = enrollment.calculate_progress()
            if abs(enrollment.progress_percentage - current_progress) > 0.1:
                enrollment.progress_percentage = current_progress
                if current_progress >= 100 and enrollment.status == 'active':
                    enrollment.status = 'completed'
                    enrollment.completed_at = datetime.now()
        
        db.session.commit()
        
        for enrollment in enrollments:
            student = enrollment.student
            progress = TeacherService._calculate_detailed_student_progress(student.id, course_id)
            last_activity = TeacherService._get_last_activity(student.id, course_id)
            
            student_reports.append({
                'student': student.to_dict(),
                'enrollment': enrollment.to_dict(),
                'progress': progress,
                'last_activity': last_activity.isoformat() if last_activity else None,
                'overall_progress': enrollment.progress_percentage
            })
        
        student_reports.sort(key=lambda x: x['overall_progress'], reverse=True)
        
        return {
            'course': course.to_dict(),
            'student_reports': student_reports,
            'total_students': len(student_reports),
            'summary': {
                'average_progress': sum([sr['overall_progress'] for sr in student_reports]) / len(student_reports) if student_reports else 0,
                'completed_students': len([sr for sr in student_reports if sr['enrollment']['status'] == 'completed']),
                'active_students': len([sr for sr in student_reports if sr['enrollment']['status'] == 'active'])
            }
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
        
        thirty_days_ago = datetime.now() - timedelta(days=30)
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
        start_date = datetime.now() - timedelta(days=30)

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

    @staticmethod
    def get_all_quiz_attempts(teacher_id: int) -> Dict[str, Any]:
        """Get all quiz attempts for teacher's courses"""
        user = User.query.get(teacher_id)
        if not user or not user.is_teacher():
            raise PermissionException("Only teachers can access quiz attempts")
        
        courses = user.taught_courses.all()
        all_attempts = []
        
        for course in courses:
            for quiz in course.quizzes:
                attempts = quiz.attempts.filter(
                    QuizAttempt.status.in_(['completed', 'in_progress'])
                ).order_by(desc(QuizAttempt.submitted_at)).all()
                
                for attempt in attempts:
                    attempt_data = attempt.to_dict()
                    attempt_data['student'] = attempt.student.to_dict()
                    attempt_data['quiz'] = quiz.to_dict()
                    attempt_data['course'] = course.to_dict()
                    
                    questions = []
                    for question in quiz.questions:
                        question_data = question.to_dict()
                        questions.append(question_data)
                    attempt_data['quiz']['questions'] = questions
                    
                    all_attempts.append(attempt_data)
        
        all_attempts.sort(key=lambda x: x.get('submitted_at') or x.get('started_at'), reverse=True)
        
        return {
            'attempts': all_attempts,
            'total': len(all_attempts)
        }

    @staticmethod
    def get_quiz_attempt_details(teacher_id: int, attempt_id: int) -> Dict[str, Any]:
        """Get detailed quiz attempt information for grading"""
        user = User.query.get(teacher_id)
        if not user or not user.is_teacher():
            raise PermissionException("Only teachers can access quiz attempt details")
        
        attempt = QuizAttempt.query.get(attempt_id)
        if not attempt:
            raise NotFoundException("Quiz attempt not found")
        
        quiz = attempt.quiz
        if quiz.course.teacher_id != teacher_id:
            raise PermissionException("Access denied to this quiz attempt")
        
        attempt_data = attempt.to_dict()
        attempt_data['student'] = attempt.student.to_dict()
        attempt_data['quiz'] = quiz.to_dict()
        attempt_data['course'] = quiz.course.to_dict()
        
        questions = []
        student_answers = {sa.question_id: sa for sa in attempt.student_answers}
        
        for question in quiz.questions.order_by(Question.order_number):
            question_data = question.to_dict()
            student_answer = student_answers.get(question.id)
            
            if student_answer:
                question_data['student_answer'] = student_answer.answer_text if question.question_type == 'short_answer' else None
                question_data['selected_option_id'] = student_answer.selected_option_id
                question_data['is_correct'] = student_answer.is_correct
                question_data['points_earned'] = student_answer.points_earned
                question_data['answer_id'] = student_answer.id
                
                if student_answer.selected_option:
                    question_data['selected_option_text'] = student_answer.selected_option.option_text
            
            questions.append(question_data)
        
        attempt_data['questions'] = questions
        
        return attempt_data

    @staticmethod
    def get_quiz_grading_summary(teacher_id: int) -> Dict[str, Any]:
        """Get summary statistics for quiz grading dashboard"""
        user = User.query.get(teacher_id)
        if not user or not user.is_teacher():
            raise PermissionException("Only teachers can access grading summary")
        
        courses = user.taught_courses.all()
        
        total_attempts = 0
        pending_grading = 0
        graded_today = 0
        total_score = 0
        completed_attempts = 0
        failed_attempts = 0
        
        today = datetime.now().date()
        
        for course in courses:
            for quiz in course.quizzes:
                attempts = quiz.attempts.filter_by(status='completed').all()
                total_attempts += len(attempts)
                
                has_short_answer = any(q.question_type == 'short_answer' for q in quiz.questions)
                
                for attempt in attempts:
                    if has_short_answer and not attempt.graded_at:
                        pending_grading += 1
                    
                    if attempt.graded_at and attempt.graded_at.date() == today:
                        graded_today += 1
                    
                    if attempt.score is not None:
                        total_score += attempt.score
                        completed_attempts += 1
                        
                        if attempt.score < quiz.passing_score:
                            failed_attempts += 1
        
        avg_score = total_score / completed_attempts if completed_attempts > 0 else 0
        
        return {
            'total_attempts': total_attempts,
            'pending_grading': pending_grading,
            'graded_today': graded_today,
            'average_score': round(avg_score, 1),
            'failed_attempts': failed_attempts,
            'completed_attempts': completed_attempts
        }