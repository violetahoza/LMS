from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import desc, func
from app.models import db, User, Quiz, QuizAttempt, Course, Enrollment
from app.utils.base_controller import ValidationException, PermissionException, NotFoundException

class QuizHistoryService:
    """Service for student quiz results history"""
    
    @staticmethod
    def get_student_quiz_history(student_id: int, course_id: Optional[int] = None, 
                               page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Get comprehensive quiz history for a student"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise PermissionException("Only students can access quiz history")
        
        query = QuizAttempt.query.filter_by(student_id=student_id)
        
        if course_id:
            query = query.join(Quiz).filter(Quiz.course_id == course_id)
        
        query = query.order_by(desc(QuizAttempt.submitted_at))
        
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        history_data = []
        for attempt in pagination.items:
            quiz = attempt.quiz
            course = quiz.course
            
            performance_data = QuizHistoryService._calculate_attempt_performance(attempt)
            
            history_item = {
                'attempt_id': attempt.id,
                'quiz_id': quiz.id,
                'quiz_title': quiz.title,
                'course_id': course.id,
                'course_title': course.title,
                'teacher_name': course.teacher.full_name if course.teacher else None,
                'attempt_number': attempt.attempt_number,
                'score': attempt.score,
                'max_score': quiz.total_points,
                'passing_score': quiz.passing_score,
                'passed': attempt.score >= quiz.passing_score if attempt.score is not None else False,
                'submitted_at': attempt.submitted_at.isoformat() if attempt.submitted_at else None,
                'time_spent_minutes': attempt.time_spent_minutes,
                'status': attempt.status,
                'performance': performance_data
            }
            
            history_data.append(history_item)
        
        stats = QuizHistoryService._calculate_overall_stats(student_id, course_id)
        
        return {
            'quiz_history': history_data,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages,
            'statistics': stats
        }
    
    @staticmethod
    def get_quiz_attempt_details(student_id: int, attempt_id: int) -> Dict[str, Any]:
        """Get detailed information about a specific quiz attempt"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise PermissionException("Only students can access quiz attempts")
        
        attempt = QuizAttempt.query.get(attempt_id)
        if not attempt:
            raise NotFoundException("Quiz attempt not found")
        
        if attempt.student_id != student_id:
            raise PermissionException("Access denied to this quiz attempt")
        
        from app.services.quiz_service import QuizService
        results = QuizService._get_detailed_results(attempt_id)
        
        other_attempts = QuizAttempt.query.filter_by(
            student_id=student_id,
            quiz_id=attempt.quiz_id
        ).filter(QuizAttempt.id != attempt_id).order_by(QuizAttempt.attempt_number).all()
        
        comparison_data = []
        for other_attempt in other_attempts:
            comparison_data.append({
                'attempt_number': other_attempt.attempt_number,
                'score': other_attempt.score,
                'submitted_at': other_attempt.submitted_at.isoformat() if other_attempt.submitted_at else None,
                'time_spent_minutes': other_attempt.time_spent_minutes
            })
        
        results['attempt_comparison'] = comparison_data
        results['performance_analysis'] = QuizHistoryService._analyze_performance_trends(student_id, attempt.quiz_id)
        
        return results
    
    @staticmethod
    def get_quiz_performance_analytics(student_id: int, quiz_id: int) -> Dict[str, Any]:
        """Get performance analytics for a specific quiz"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise PermissionException("Only students can access quiz analytics")
        
        quiz = Quiz.query.get(quiz_id)
        if not quiz:
            raise NotFoundException("Quiz not found")
        
        enrollment = Enrollment.query.filter_by(
            student_id=student_id,
            course_id=quiz.course_id
        ).filter(Enrollment.status.in_(['active', 'completed'])).first()
        
        if not enrollment:
            raise PermissionException("Not enrolled in this course")
        
        attempts = QuizAttempt.query.filter_by(
            student_id=student_id,
            quiz_id=quiz_id,
            status='completed'
        ).order_by(QuizAttempt.attempt_number).all()
        
        if not attempts:
            return {
                'quiz': quiz.to_dict(),
                'no_attempts': True,
                'message': 'No completed attempts found'
            }
        
        score_trend = [attempt.score for attempt in attempts if attempt.score is not None]
        time_trend = [attempt.time_spent_minutes for attempt in attempts if attempt.time_spent_minutes]
        
        best_attempt = max(attempts, key=lambda a: a.score or 0)
        worst_attempt = min(attempts, key=lambda a: a.score or 0)
        
        question_performance = QuizHistoryService._analyze_question_performance(attempts)
        
        improvement_data = QuizHistoryService._calculate_improvement_metrics(attempts)
        
        return {
            'quiz': quiz.to_dict(),
            'total_attempts': len(attempts),
            'score_trend': score_trend,
            'time_trend': time_trend,
            'best_attempt': {
                'attempt_number': best_attempt.attempt_number,
                'score': best_attempt.score,
                'submitted_at': best_attempt.submitted_at.isoformat() if best_attempt.submitted_at else None
            },
            'worst_attempt': {
                'attempt_number': worst_attempt.attempt_number,
                'score': worst_attempt.score,
                'submitted_at': worst_attempt.submitted_at.isoformat() if worst_attempt.submitted_at else None
            },
            'question_performance': question_performance,
            'improvement_metrics': improvement_data,
            'current_status': {
                'best_score': max(score_trend) if score_trend else 0,
                'average_score': sum(score_trend) / len(score_trend) if score_trend else 0,
                'passed': any(score >= quiz.passing_score for score in score_trend),
                'attempts_remaining': max(0, quiz.max_attempts - len(attempts))
            }
        }
    
    @staticmethod
    def get_course_quiz_summary(student_id: int, course_id: int) -> Dict[str, Any]:
        """Get summary of all quizzes in a course for a student"""
        user = User.query.get(student_id)
        if not user or not user.is_student():
            raise PermissionException("Only students can access quiz summaries")
        
        course = Course.query.get(course_id)
        if not course:
            raise NotFoundException("Course not found")
        
        enrollment = Enrollment.query.filter_by(
            student_id=student_id,
            course_id=course_id
        ).filter(Enrollment.status.in_(['active', 'completed'])).first()
        
        if not enrollment:
            raise PermissionException("Not enrolled in this course")
        
        quizzes = Quiz.query.filter_by(course_id=course_id).all()
        quiz_summaries = []
        
        for quiz in quizzes:
            attempts = QuizAttempt.query.filter_by(
                student_id=student_id,
                quiz_id=quiz.id,
                status='completed'
            ).all()
            
            if attempts:
                best_score = max(attempt.score for attempt in attempts if attempt.score is not None)
                total_attempts = len(attempts)
                passed = best_score >= quiz.passing_score
                last_attempt = max(attempts, key=lambda a: a.submitted_at or datetime.min)
            else:
                best_score = 0
                total_attempts = 0
                passed = False
                last_attempt = None
            
            quiz_summaries.append({
                'quiz_id': quiz.id,
                'quiz_title': quiz.title,
                'best_score': best_score,
                'passing_score': quiz.passing_score,
                'total_attempts': total_attempts,
                'max_attempts': quiz.max_attempts,
                'passed': passed,
                'attempts_remaining': max(0, quiz.max_attempts - total_attempts),
                'last_attempt_date': last_attempt.submitted_at.isoformat() if last_attempt and last_attempt.submitted_at else None,
                'can_retake': total_attempts < quiz.max_attempts
            })
        
        total_quizzes = len(quizzes)
        attempted_quizzes = sum(1 for summary in quiz_summaries if summary['total_attempts'] > 0)
        passed_quizzes = sum(1 for summary in quiz_summaries if summary['passed'])
        
        return {
            'course': course.to_dict(),
            'quiz_summaries': quiz_summaries,
            'course_statistics': {
                'total_quizzes': total_quizzes,
                'attempted_quizzes': attempted_quizzes,
                'passed_quizzes': passed_quizzes,
                'completion_rate': (attempted_quizzes / total_quizzes * 100) if total_quizzes > 0 else 0,
                'pass_rate': (passed_quizzes / attempted_quizzes * 100) if attempted_quizzes > 0 else 0
            }
        }
    
    @staticmethod
    def _calculate_attempt_performance(attempt: QuizAttempt) -> Dict[str, Any]:
        """Calculate performance metrics for a single attempt"""
        total_questions = len(attempt.student_answers)
        correct_answers = sum(1 for ans in attempt.student_answers if ans.is_correct)
        
        return {
            'total_questions': total_questions,
            'correct_answers': correct_answers,
            'incorrect_answers': total_questions - correct_answers,
            'accuracy_rate': (correct_answers / total_questions * 100) if total_questions > 0 else 0,
            'points_earned': sum(ans.points_earned or 0 for ans in attempt.student_answers),
            'total_points': sum(ans.question.points for ans in attempt.student_answers)
        }
    
    @staticmethod
    def _calculate_overall_stats(student_id: int, course_id: Optional[int] = None) -> Dict[str, Any]:
        """Calculate overall quiz statistics for a student"""
        query = QuizAttempt.query.filter_by(student_id=student_id, status='completed')
        
        if course_id:
            query = query.join(Quiz).filter(Quiz.course_id == course_id)
        
        attempts = query.all()
        
        if not attempts:
            return {
                'total_attempts': 0,
                'total_quizzes': 0,
                'average_score': 0,
                'best_score': 0,
                'total_time_spent': 0
            }
        
        scores = [attempt.score for attempt in attempts if attempt.score is not None]
        unique_quizzes = len(set(attempt.quiz_id for attempt in attempts))
        
        return {
            'total_attempts': len(attempts),
            'total_quizzes': unique_quizzes,
            'average_score': sum(scores) / len(scores) if scores else 0,
            'best_score': max(scores) if scores else 0,
            'worst_score': min(scores) if scores else 0,
            'total_time_spent': sum(attempt.time_spent_minutes or 0 for attempt in attempts),
            'average_time_per_attempt': sum(attempt.time_spent_minutes or 0 for attempt in attempts) / len(attempts)
        }
    
    @staticmethod
    def _analyze_performance_trends(student_id: int, quiz_id: int) -> Dict[str, Any]:
        """Analyze performance trends for a specific quiz"""
        attempts = QuizAttempt.query.filter_by(
            student_id=student_id,
            quiz_id=quiz_id,
            status='completed'
        ).order_by(QuizAttempt.attempt_number).all()
        
        if len(attempts) < 2:
            return {'insufficient_data': True}
        
        scores = [attempt.score for attempt in attempts if attempt.score is not None]
        
        if len(scores) >= 2:
            trend = 'improving' if scores[-1] > scores[0] else 'declining' if scores[-1] < scores[0] else 'stable'
            improvement = scores[-1] - scores[0] if len(scores) >= 2 else 0
        else:
            trend = 'unknown'
            improvement = 0
        
        return {
            'trend': trend,
            'improvement': improvement,
            'consistency': QuizHistoryService._calculate_consistency(scores),
            'peak_performance': max(scores) if scores else 0,
            'performance_variance': QuizHistoryService._calculate_variance(scores)
        }
    
    @staticmethod
    def _analyze_question_performance(attempts: List[QuizAttempt]) -> List[Dict[str, Any]]:
        """Analyze performance on individual questions across attempts"""
        question_stats = {}
        
        for attempt in attempts:
            for answer in attempt.student_answers:
                question_id = answer.question_id
                if question_id not in question_stats:
                    question_stats[question_id] = {
                        'question_text': answer.question.question_text,
                        'total_attempts': 0,
                        'correct_attempts': 0,
                        'points': answer.question.points
                    }
                
                question_stats[question_id]['total_attempts'] += 1
                if answer.is_correct:
                    question_stats[question_id]['correct_attempts'] += 1
        
        return [
            {
                'question_id': qid,
                'question_text': stats['question_text'],
                'accuracy_rate': (stats['correct_attempts'] / stats['total_attempts'] * 100) if stats['total_attempts'] > 0 else 0,
                'total_attempts': stats['total_attempts'],
                'correct_attempts': stats['correct_attempts'],
                'points': stats['points']
            }
            for qid, stats in question_stats.items()
        ]
    
    @staticmethod
    def _calculate_improvement_metrics(attempts: List[QuizAttempt]) -> Dict[str, Any]:
        """Calculate improvement metrics"""
        if len(attempts) < 2:
            return {'insufficient_data': True}
        
        scores = [attempt.score for attempt in attempts if attempt.score is not None]
        
        return {
            'first_attempt_score': scores[0] if scores else 0,
            'last_attempt_score': scores[-1] if scores else 0,
            'total_improvement': scores[-1] - scores[0] if len(scores) >= 2 else 0,
            'best_improvement_streak': QuizHistoryService._find_best_streak(scores),
            'average_improvement_per_attempt': QuizHistoryService._calculate_average_improvement(scores)
        }
    
    @staticmethod
    def _calculate_consistency(scores: List[float]) -> float:
        """Calculate consistency score (lower variance = higher consistency)"""
        if len(scores) < 2:
            return 100.0
        
        variance = QuizHistoryService._calculate_variance(scores)
        return max(0, 100 - variance)
    
    @staticmethod
    def _calculate_variance(scores: List[float]) -> float:
        """Calculate variance of scores"""
        if len(scores) < 2:
            return 0
        
        mean = sum(scores) / len(scores)
        variance = sum((score - mean) ** 2 for score in scores) / len(scores)
        return variance
    
    @staticmethod
    def _find_best_streak(scores: List[float]) -> int:
        """Find the longest streak of improving scores"""
        if len(scores) < 2:
            return 0
        
        best_streak = 0
        current_streak = 0
        
        for i in range(1, len(scores)):
            if scores[i] > scores[i-1]:
                current_streak += 1
                best_streak = max(best_streak, current_streak)
            else:
                current_streak = 0
        
        return best_streak
    
    @staticmethod
    def _calculate_average_improvement(scores: List[float]) -> float:
        """Calculate average improvement per attempt"""
        if len(scores) < 2:
            return 0
        
        improvements = []
        for i in range(1, len(scores)):
            improvements.append(scores[i] - scores[i-1])
        
        return sum(improvements) / len(improvements) if improvements else 0