from datetime import datetime
from typing import Dict, Any, List
from app.models import db, Quiz, QuizAttempt, Question, StudentAnswer, User
from app.utils.base_controller import ValidationException, PermissionException, NotFoundException
from app.services.notification_service import NotificationService

class QuizGradingService:
    """Service for manual quiz grading (especially short answers)"""
    
    @staticmethod
    def get_pending_quiz_grading(teacher_id: int) -> Dict[str, Any]:
        """Get quiz attempts that need manual grading"""
        teacher = User.query.get(teacher_id)
        if not teacher or not teacher.is_teacher():
            raise PermissionException("Only teachers can access quiz grading")
        
        teacher_quizzes = Quiz.query.join(Quiz.course).filter(
            Quiz.course.has(teacher_id=teacher_id)
        ).all()
        
        pending_attempts = []
        
        for quiz in teacher_quizzes:
            attempts = QuizAttempt.query.filter_by(
                quiz_id=quiz.id,
                status='completed'
            ).all()
            
            for attempt in attempts:
                has_ungraded = False
                ungraded_questions = []
                
                for answer in attempt.student_answers:
                    if (answer.question.question_type == 'short_answer' and 
                        answer.is_correct is None):
                        has_ungraded = True
                        ungraded_questions.append({
                            'question_id': answer.question_id,
                            'question_text': answer.question.question_text,
                            'answer_text': answer.answer_text,
                            'points': answer.question.points
                        })
                
                if has_ungraded:
                    pending_attempts.append({
                        'attempt_id': attempt.id,
                        'student_name': attempt.student.full_name,
                        'quiz_title': quiz.title,
                        'course_title': quiz.course.title,
                        'submitted_at': attempt.submitted_at.isoformat() if attempt.submitted_at else None,
                        'current_score': attempt.score,
                        'ungraded_questions': ungraded_questions,
                        'total_ungraded': len(ungraded_questions)
                    })
        
        return {
            'pending_attempts': pending_attempts,
            'total': len(pending_attempts)
        }
    
    @staticmethod
    def get_attempt_for_grading(teacher_id: int, attempt_id: int) -> Dict[str, Any]:
        """Get detailed quiz attempt for grading"""
        teacher = User.query.get(teacher_id)
        if not teacher or not teacher.is_teacher():
            raise PermissionException("Only teachers can access quiz grading")
        
        attempt = QuizAttempt.query.get(attempt_id)
        if not attempt:
            raise NotFoundException("Quiz attempt not found")
        
        if attempt.quiz.course.teacher_id != teacher_id:
            raise PermissionException("Access denied to this quiz attempt")
        
        questions_data = []
        for answer in attempt.student_answers:
            question = answer.question
            question_data = {
                'question_id': question.id,
                'question_text': question.question_text,
                'question_type': question.question_type,
                'points': question.points,
                'answer_id': answer.id,
                'student_answer': answer.answer_text,
                'selected_option_id': answer.selected_option_id,
                'is_correct': answer.is_correct,
                'points_earned': answer.points_earned,
                'needs_grading': (question.question_type == 'short_answer' and answer.is_correct is None)
            }
            
            if question.question_type in ['multiple_choice', 'true_false']:
                question_data['options'] = [
                    {
                        'id': opt.id,
                        'option_text': opt.option_text,
                        'is_correct': opt.is_correct,
                        'selected': opt.id == answer.selected_option_id
                    }
                    for opt in question.answer_options
                ]
            
            questions_data.append(question_data)
        
        return {
            'attempt': attempt.to_dict(),
            'student': attempt.student.to_dict(),
            'quiz': attempt.quiz.to_dict(),
            'course': attempt.quiz.course.to_dict(),
            'questions': questions_data,
            'grading_complete': all(
                q['is_correct'] is not None or q['question_type'] != 'short_answer'
                for q in questions_data
            )
        }
    
    @staticmethod
    def grade_short_answer(teacher_id: int, answer_id: int, is_correct: bool, points_awarded: float = None) -> Dict[str, Any]:
        """Grade a specific short answer question"""
        teacher = User.query.get(teacher_id)
        if not teacher or not teacher.is_teacher():
            raise PermissionException("Only teachers can grade quiz answers")
        
        answer = StudentAnswer.query.get(answer_id)
        if not answer:
            raise NotFoundException("Answer not found")
        
        if answer.attempt.quiz.course.teacher_id != teacher_id:
            raise PermissionException("Access denied to this quiz answer")
        
        if answer.question.question_type != 'short_answer':
            raise ValidationException("This method is only for short answer questions")
        
        max_points = answer.question.points
        if points_awarded is None:
            points_awarded = max_points if is_correct else 0
        
        if points_awarded < 0 or points_awarded > max_points:
            raise ValidationException(f"Points must be between 0 and {max_points}")
        
        answer.is_correct = is_correct
        answer.points_earned = points_awarded
        
        attempt = answer.attempt
        total_points = sum(ans.question.points for ans in attempt.student_answers)
        earned_points = sum(ans.points_earned or 0 for ans in attempt.student_answers)
        
        old_score = attempt.score
        attempt.score = (earned_points / total_points * 100) if total_points > 0 else 0
        
        db.session.commit()
        
        all_graded = all(
            ans.is_correct is not None or ans.question.question_type != 'short_answer'
            for ans in attempt.student_answers
        )
        
        result = {
            'message': 'Answer graded successfully',
            'answer_id': answer_id,
            'is_correct': is_correct,
            'points_awarded': points_awarded,
            'old_score': old_score,
            'new_score': attempt.score,
            'all_graded': all_graded
        }
        
        if all_graded and abs(attempt.score - old_score) > 0.1:
            NotificationService.notify_quiz_graded(
                student_id=attempt.student_id,
                teacher_id=teacher_id,
                quiz_id=attempt.quiz_id,
                score=attempt.score
            )
            result['notification_sent'] = True
        
        return result
    
    @staticmethod
    def bulk_grade_answers(teacher_id: int, grading_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Grade multiple short answer questions at once"""
        teacher = User.query.get(teacher_id)
        if not teacher or not teacher.is_teacher():
            raise PermissionException("Only teachers can grade quiz answers")
        
        results = []
        errors = []
        
        for grade_item in grading_data:
            try:
                result = QuizGradingService.grade_short_answer(
                    teacher_id=teacher_id,
                    answer_id=grade_item['answer_id'],
                    is_correct=grade_item['is_correct'],
                    points_awarded=grade_item.get('points_awarded')
                )
                results.append(result)
            except Exception as e:
                errors.append({
                    'answer_id': grade_item['answer_id'],
                    'error': str(e)
                })
        
        return {
            'graded_answers': results,
            'errors': errors,
            'total_graded': len(results),
            'total_errors': len(errors)
        }
    
    @staticmethod
    def get_quiz_grading_history(teacher_id: int, quiz_id: int) -> Dict[str, Any]:
        """Get grading history for a specific quiz"""
        teacher = User.query.get(teacher_id)
        if not teacher or not teacher.is_teacher():
            raise PermissionException("Only teachers can access grading history")
        
        quiz = Quiz.query.get(quiz_id)
        if not quiz:
            raise NotFoundException("Quiz not found")
        
        if quiz.course.teacher_id != teacher_id:
            raise PermissionException("Access denied to this quiz")
        
        attempts = QuizAttempt.query.filter_by(
            quiz_id=quiz_id,
            status='completed'
        ).order_by(QuizAttempt.submitted_at.desc()).all()
        
        grading_history = []
        for attempt in attempts:
            short_answer_count = sum(
                1 for ans in attempt.student_answers 
                if ans.question.question_type == 'short_answer'
            )
            graded_short_answers = sum(
                1 for ans in attempt.student_answers 
                if ans.question.question_type == 'short_answer' and ans.is_correct is not None
            )
            
            grading_history.append({
                'attempt_id': attempt.id,
                'student_name': attempt.student.full_name,
                'submitted_at': attempt.submitted_at.isoformat() if attempt.submitted_at else None,
                'score': attempt.score,
                'short_answer_questions': short_answer_count,
                'graded_short_answers': graded_short_answers,
                'grading_complete': graded_short_answers == short_answer_count,
                'needs_grading': short_answer_count > graded_short_answers
            })
        
        return {
            'quiz': quiz.to_dict(),
            'grading_history': grading_history,
            'total_attempts': len(grading_history),
            'pending_grading': sum(1 for h in grading_history if h['needs_grading'])
        }