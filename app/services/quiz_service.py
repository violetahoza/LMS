from datetime import datetime, timedelta
from app.models import db, Quiz, QuizAttempt, Question, AnswerOption, StudentAnswer
from app.utils.helpers import calculate_time_spent

class QuizService:
    """Service class for quiz-related operations"""
    
    @staticmethod
    def create_quiz_attempt(quiz_id, student_id):
        """Create a new quiz attempt"""
        quiz = Quiz.query.get(quiz_id)
        if not quiz:
            raise ValueError("Quiz not found")
        
        # Check if student has reached max attempts
        existing_attempts = QuizAttempt.query.filter_by(
            quiz_id=quiz_id,
            student_id=student_id
        ).count()
        
        if existing_attempts >= quiz.max_attempts:
            raise ValueError(f"Maximum attempts ({quiz.max_attempts}) reached")
        
        # Create new attempt
        attempt = QuizAttempt(
            quiz_id=quiz_id,
            student_id=student_id,
            attempt_number=existing_attempts + 1,
            status='in_progress'
        )
        
        db.session.add(attempt)
        db.session.commit()
        
        return attempt
    
    @staticmethod
    def get_quiz_questions(quiz_id, include_answers=False):
        """Get all questions for a quiz"""
        questions = Question.query.filter_by(quiz_id=quiz_id).order_by(Question.order_number).all()
        
        questions_data = []
        for question in questions:
            q_data = {
                'id': question.id,
                'question_text': question.question_text,
                'question_type': question.question_type,
                'points': question.points,
                'order_number': question.order_number
            }
            
            if question.question_type in ['multiple_choice', 'true_false']:
                options = []
                for option in question.answer_options:
                    opt_data = {
                        'id': option.id,
                        'option_text': option.option_text
                    }
                    if include_answers:
                        opt_data['is_correct'] = option.is_correct
                    options.append(opt_data)
                q_data['options'] = options
            
            questions_data.append(q_data)
        
        return questions_data
    
    @staticmethod
    def submit_quiz_attempt(attempt_id, answers):
        """Submit and grade a quiz attempt"""
        attempt = QuizAttempt.query.get(attempt_id)
        if not attempt:
            raise ValueError("Quiz attempt not found")
        
        if attempt.status != 'in_progress':
            raise ValueError("Quiz has already been submitted")
        
        # Check time limit
        if attempt.quiz.time_limit_minutes:
            time_spent = calculate_time_spent(attempt.started_at)
            if time_spent > attempt.quiz.time_limit_minutes:
                attempt.status = 'abandoned'
                db.session.commit()
                raise ValueError("Time limit exceeded")
        
        # Save and grade answers
        total_points = 0
        earned_points = 0
        
        for question_id, answer_value in answers.items():
            question = Question.query.get(int(question_id))
            if not question or question.quiz_id != attempt.quiz_id:
                continue
            
            total_points += question.points
            
            student_answer = StudentAnswer(
                attempt_id=attempt_id,
                question_id=question.id
            )
            
            # Grade based on question type
            if question.question_type == 'multiple_choice':
                student_answer.selected_option_id = answer_value
                selected_option = AnswerOption.query.get(answer_value)
                if selected_option and selected_option.is_correct:
                    student_answer.is_correct = True
                    student_answer.points_earned = question.points
                    earned_points += question.points
                else:
                    student_answer.is_correct = False
                    student_answer.points_earned = 0
            
            elif question.question_type == 'true_false':
                student_answer.selected_option_id = answer_value
                selected_option = AnswerOption.query.get(answer_value)
                if selected_option and selected_option.is_correct:
                    student_answer.is_correct = True
                    student_answer.points_earned = question.points
                    earned_points += question.points
                else:
                    student_answer.is_correct = False
                    student_answer.points_earned = 0
            
            elif question.question_type == 'short_answer':
                student_answer.answer_text = answer_value
                # Short answer questions need manual grading
                student_answer.is_correct = None
                student_answer.points_earned = 0
            
            db.session.add(student_answer)
        
        # Calculate score
        attempt.score = (earned_points / total_points * 100) if total_points > 0 else 0
        attempt.submitted_at = datetime.utcnow()
        attempt.time_spent_minutes = calculate_time_spent(attempt.started_at, attempt.submitted_at)
        attempt.status = 'completed'
        
        db.session.commit()
        
        return {
            'score': attempt.score,
            'earned_points': earned_points,
            'total_points': total_points,
            'passed': attempt.score >= attempt.quiz.passing_score
        }
    
    @staticmethod
    def get_quiz_results(attempt_id):
        """Get detailed results for a quiz attempt"""
        attempt = QuizAttempt.query.get(attempt_id)
        if not attempt:
            raise ValueError("Quiz attempt not found")
        
        if attempt.status != 'completed':
            raise ValueError("Quiz has not been completed")
        
        results = {
            'attempt': attempt.to_dict(),
            'quiz': attempt.quiz.to_dict(),
            'questions': []
        }
        
        for answer in attempt.student_answers:
            question = answer.question
            question_data = {
                'id': question.id,
                'question_text': question.question_text,
                'question_type': question.question_type,
                'points': question.points,
                'student_answer': None,
                'correct_answer': None,
                'is_correct': answer.is_correct,
                'points_earned': answer.points_earned
            }
            
            if question.question_type in ['multiple_choice', 'true_false']:
                # Get student's selected option
                if answer.selected_option:
                    question_data['student_answer'] = answer.selected_option.option_text
                
                # Get correct option(s)
                correct_options = [opt.option_text for opt in question.answer_options if opt.is_correct]
                question_data['correct_answer'] = correct_options[0] if correct_options else None
                
                # Include all options
                question_data['options'] = [
                    {
                        'id': opt.id,
                        'option_text': opt.option_text,
                        'is_correct': opt.is_correct,
                        'selected': opt.id == answer.selected_option_id
                    }
                    for opt in question.answer_options
                ]
            else:
                question_data['student_answer'] = answer.answer_text
            
            results['questions'].append(question_data)
        
        return results
    
    @staticmethod
    def get_student_quiz_attempts(student_id, quiz_id=None):
        """Get all quiz attempts for a student"""
        query = QuizAttempt.query.filter_by(student_id=student_id)
        
        if quiz_id:
            query = query.filter_by(quiz_id=quiz_id)
        
        attempts = query.order_by(QuizAttempt.started_at.desc()).all()
        
        return [attempt.to_dict() for attempt in attempts]
    
    @staticmethod
    def can_retake_quiz(student_id, quiz_id):
        """Check if student can retake a quiz"""
        quiz = Quiz.query.get(quiz_id)
        if not quiz:
            return False, "Quiz not found"
        
        attempts = QuizAttempt.query.filter_by(
            student_id=student_id,
            quiz_id=quiz_id
        ).count()
        
        if attempts >= quiz.max_attempts:
            return False, f"Maximum attempts ({quiz.max_attempts}) reached"
        
        # Check if there's an in-progress attempt
        in_progress = QuizAttempt.query.filter_by(
            student_id=student_id,
            quiz_id=quiz_id,
            status='in_progress'
        ).first()
        
        if in_progress:
            return False, "You have an in-progress attempt"
        
        return True, f"You have {quiz.max_attempts - attempts} attempts remaining"
    
    @staticmethod
    def auto_submit_expired_attempts():
        """Auto-submit quiz attempts that have exceeded time limit"""
        # Find all in-progress attempts with time limits
        expired_attempts = db.session.query(QuizAttempt).join(Quiz).filter(
            QuizAttempt.status == 'in_progress',
            Quiz.time_limit_minutes.isnot(None)
        ).all()
        
        count = 0
        for attempt in expired_attempts:
            time_spent = calculate_time_spent(attempt.started_at)
            if time_spent > attempt.quiz.time_limit_minutes:
                # Auto-submit with current answers
                existing_answers = {
                    str(sa.question_id): sa.selected_option_id or sa.answer_text
                    for sa in attempt.student_answers
                }
                
                try:
                    QuizService.submit_quiz_attempt(attempt.id, existing_answers)
                    count += 1
                except Exception:
                    # If submission fails, mark as abandoned
                    attempt.status = 'abandoned'
                    attempt.submitted_at = datetime.utcnow()
                    db.session.commit()
        
        return count