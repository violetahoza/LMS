from datetime import datetime, timedelta
from typing import Dict, Any, List
from app.models import db, Quiz, QuizAttempt, Question, AnswerOption, StudentAnswer, User, Course, Enrollment
from app.services.achievement_service import AchievementService
from app.utils.base_controller import ValidationException, PermissionException, NotFoundException
from app.utils.helpers import calculate_time_spent, calculate_quiz_statistics
from app.utils.validators import validate_quiz_answers

class QuizService:
    """Service class for quiz-related operations"""
    
    @staticmethod
    def get_course_quizzes(user_id: int, course_id: int) -> Dict[str, Any]:
        """Get all quizzes for a course"""
        user = User.query.get(user_id)
        course = Course.query.get(course_id)
        
        if not course:
            raise NotFoundException("Course not found")
        
        if not user.can_access_course(course):
            raise PermissionException("Access denied")
        
        quizzes = course.quizzes.all()
        quizzes_data = []
        
        for quiz in quizzes:
            quiz_dict = quiz.to_dict()
            
            if user.is_student():
                attempts = QuizAttempt.query.filter_by(
                    student_id=user_id,
                    quiz_id=quiz.id
                ).all()
                
                quiz_dict['attempts'] = {
                    'count': len(attempts),
                    'remaining': quiz.max_attempts - len(attempts),
                    'best_score': max([a.score for a in attempts if a.score is not None], default=0) if attempts else 0,
                    'has_passed': any(a.score >= quiz.passing_score for a in attempts if a.score is not None)
                }
            
            quiz_dict['question_count'] = quiz.questions.count()
            
            quizzes_data.append(quiz_dict)
        
        return {
            'quizzes': quizzes_data,
            'total': len(quizzes_data)
        }
    
    @staticmethod
    def get_quiz(user_id: int, quiz_id: int) -> Dict[str, Any]:
        """Get a specific quiz with questions"""
        user = User.query.get(user_id)
        quiz = Quiz.query.get(quiz_id)
        
        if not quiz:
            raise NotFoundException("Quiz not found")
        
        if not user.can_access_course(quiz.course):
            raise PermissionException("Access denied")
        
        quiz_data = quiz.to_dict()
        
        if user.is_teacher() and quiz.course.teacher_id == user_id:
            questions = quiz.questions.order_by(Question.order_number).all()
            quiz_data['questions'] = [
                {
                    'id': q.id,
                    'question_text': q.question_text,
                    'question_type': q.question_type,
                    'points': q.points,
                    'order_number': q.order_number,
                    'answer_options': [
                        {
                            'id': opt.id,
                            'option_text': opt.option_text,
                            'is_correct': opt.is_correct
                        }
                        for opt in q.answer_options
                    ] if q.question_type in ['multiple_choice', 'true_false'] else []
                }
                for q in questions
            ]
        
        if user.is_student():
            can_retake, message = QuizService.can_retake_quiz(user_id, quiz_id)
            quiz_data['can_take'] = can_retake
            quiz_data['message'] = message
            quiz_data['attempts'] = QuizService.get_student_quiz_attempts(user_id, quiz_id)
        
        return quiz_data
    
    @staticmethod
    def create_quiz(teacher_id: int, quiz_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new quiz"""
        required_fields = ['course_id', 'title']
        for field in required_fields:
            if field not in quiz_data:
                raise ValidationException(f'{field} is required')
        
        course = Course.query.get(quiz_data['course_id'])
        if not course:
            raise NotFoundException("Course not found")
        
        if course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        quiz = Quiz(
            course_id=quiz_data['course_id'],
            lesson_id=quiz_data.get('lesson_id'),
            title=quiz_data['title'],
            description=quiz_data.get('description'),
            total_points=quiz_data.get('total_points', 100),
            passing_score=quiz_data.get('passing_score', 60),
            time_limit_minutes=quiz_data.get('time_limit_minutes'),
            max_attempts=quiz_data.get('max_attempts', 3)
        )
        
        db.session.add(quiz)
        db.session.commit()
        
        return {
            'message': 'Quiz created successfully',
            'quiz': quiz.to_dict()
        }
    
    @staticmethod
    def update_quiz(teacher_id: int, quiz_id: int, quiz_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a quiz"""
        quiz = Quiz.query.get(quiz_id)
        if not quiz:
            raise NotFoundException("Quiz not found")
        
        if quiz.course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        allowed_fields = ['title', 'description', 'total_points', 'passing_score', 'time_limit_minutes', 'max_attempts']
        for field in allowed_fields:
            if field in quiz_data:
                setattr(quiz, field, quiz_data[field])
        
        quiz.updated_at = datetime.utcnow()
        db.session.commit()
        
        return {
            'message': 'Quiz updated successfully',
            'quiz': quiz.to_dict()
        }
    
    @staticmethod
    def delete_quiz(teacher_id: int, quiz_id: int) -> Dict[str, str]:
        """Delete a quiz"""
        quiz = Quiz.query.get(quiz_id)
        if not quiz:
            raise NotFoundException("Quiz not found")
        
        if quiz.course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        attempt_count = quiz.attempts.count()
        if attempt_count > 0:
            raise ValidationException(f'Cannot delete quiz with {attempt_count} student attempts')
        
        db.session.delete(quiz)
        db.session.commit()
        
        return {'message': 'Quiz deleted successfully'}
    
    @staticmethod
    def add_question(teacher_id: int, quiz_id: int, question_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a question to a quiz"""
        quiz = Quiz.query.get(quiz_id)
        if not quiz:
            raise NotFoundException("Quiz not found")
        
        if quiz.course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        required_fields = ['question_text', 'question_type', 'order_number']
        for field in required_fields:
            if field not in question_data:
                raise ValidationException(f'{field} is required')
        
        existing_question = Question.query.filter_by(
            quiz_id=quiz_id,
            order_number=question_data['order_number']
        ).first()
        
        if existing_question:
            questions_to_shift = Question.query.filter(
                Question.quiz_id == quiz_id,
                Question.order_number >= question_data['order_number']
            ).all()
            
            for q in questions_to_shift:
                q.order_number += 1
        
        question = Question(
            quiz_id=quiz_id,
            question_text=question_data['question_text'],
            question_type=question_data['question_type'],
            points=question_data.get('points', 10),
            order_number=question_data['order_number']
        )
        
        db.session.add(question)
        db.session.flush()  # Get question ID
        
        if question_data['question_type'] in ['multiple_choice', 'true_false']:
            options = question_data.get('options', [])
            if not options:
                raise ValidationException("Options are required for this question type")
            
            if not any(opt.get('is_correct', False) for opt in options):
                raise ValidationException("At least one option must be marked as correct")
            
            for option in options:
                if not option.get('text', '').strip():
                    continue
                    
                answer_option = AnswerOption(
                    question_id=question.id,
                    option_text=option['text'].strip(),
                    is_correct=option.get('is_correct', False)
                )
                db.session.add(answer_option)
        
        db.session.commit()
        
        question_dict = question.to_dict()
        if question.question_type in ['multiple_choice', 'true_false']:
            question_dict['answer_options'] = [opt.to_dict() for opt in question.answer_options]
        
        return {
            'message': 'Question added successfully',
            'question': question_dict
        }
    
    @staticmethod
    def update_question(teacher_id: int, quiz_id: int, question_id: int, question_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a question"""
        quiz = Quiz.query.get(quiz_id)
        if not quiz:
            raise NotFoundException("Quiz not found")
        
        if quiz.course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        question = Question.query.get(question_id)
        if not question or question.quiz_id != quiz_id:
            raise NotFoundException("Question not found")
        
        allowed_fields = ['question_text', 'question_type', 'points', 'order_number']
        for field in allowed_fields:
            if field in question_data:
                setattr(question, field, question_data[field])
        
        if 'options' in question_data and question.question_type in ['multiple_choice', 'true_false']:
            AnswerOption.query.filter_by(question_id=question.id).delete()
            
            options = question_data['options']
            if not any(opt.get('is_correct', False) for opt in options):
                raise ValidationException("At least one option must be marked as correct")
            
            for option in options:
                if not option.get('text', '').strip():
                    continue
                    
                answer_option = AnswerOption(
                    question_id=question.id,
                    option_text=option['text'].strip(),
                    is_correct=option.get('is_correct', False)
                )
                db.session.add(answer_option)
        
        db.session.commit()
        
        question_dict = question.to_dict()
        if question.question_type in ['multiple_choice', 'true_false']:
            question_dict['answer_options'] = [opt.to_dict() for opt in question.answer_options]
        
        return {
            'message': 'Question updated successfully',
            'question': question_dict
        }
    
    @staticmethod
    def delete_question(teacher_id: int, quiz_id: int, question_id: int) -> Dict[str, str]:
        """Delete a question"""
        quiz = Quiz.query.get(quiz_id)
        if not quiz:
            raise NotFoundException("Quiz not found")
        
        if quiz.course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        question = Question.query.get(question_id)
        if not question or question.quiz_id != quiz_id:
            raise NotFoundException("Question not found")
        
        attempt_count = quiz.attempts.count()
        if attempt_count > 0:
            raise ValidationException(f'Cannot delete question from quiz with {attempt_count} student attempts')
        
        order_number = question.order_number
        
        db.session.delete(question)
        
        questions_to_shift = Question.query.filter(
            Question.quiz_id == quiz_id,
            Question.order_number > order_number
        ).all()
        
        for q in questions_to_shift:
            q.order_number -= 1
        
        db.session.commit()
        
        return {'message': 'Question deleted successfully'}
    
    @staticmethod
    def start_quiz(student_id: int, quiz_id: int) -> Dict[str, Any]:
        """Start a quiz attempt"""
        quiz = Quiz.query.get(quiz_id)
        if not quiz:
            raise NotFoundException("Quiz not found")
        
        enrollment = Enrollment.query.filter_by(
            student_id=student_id,
            course_id=quiz.course_id,
            status='active'
        ).first()
        
        if not enrollment:
            raise PermissionException("Not enrolled in this course")
        
        can_take, message = QuizService.can_retake_quiz(student_id, quiz_id)
        if not can_take:
            raise ValidationException(message)
        
        attempt = QuizService.create_quiz_attempt(quiz_id, student_id)
        
        questions = QuizService.get_quiz_questions(quiz_id, include_answers=False)
        
        return {
            'attempt_id': attempt.id,
            'quiz': quiz.to_dict(),
            'questions': questions,
            'started_at': attempt.started_at.isoformat()
        }
    
    @staticmethod
    def submit_quiz_with_achievements(student_id: int, attempt_id: int, answers: Dict[str, Any]) -> Dict[str, Any]:
        """Submit quiz and check for achievements"""
        attempt = QuizAttempt.query.get(attempt_id)
        if not attempt:
            raise NotFoundException("Quiz attempt not found")
        
        if attempt.student_id != student_id:
            raise PermissionException("Access denied")
        
        questions = attempt.quiz.questions.all()
        valid, errors = validate_quiz_answers(questions, answers)
        if not valid:
            raise ValidationException(f"Invalid answers: {', '.join(errors)}")
        
        result = QuizService.submit_quiz_attempt(attempt_id, answers)
        
        achievements = AchievementService.check_quiz_achievement(student_id, attempt_id)
        
        response = {
            'message': 'Quiz submitted successfully',
            'result': result
        }
        
        if achievements:
            response['achievements_earned'] = [
                {
                    'name': a.name,
                    'description': a.description,
                    'points': a.points_value
                }
                for a in achievements
            ]
        
        return response
    
    @staticmethod
    def get_quiz_results(user_id: int, attempt_id: int) -> Dict[str, Any]:
        """Get quiz results"""
        user = User.query.get(user_id)
        attempt = QuizAttempt.query.get(attempt_id)
        
        if not attempt:
            raise NotFoundException("Quiz attempt not found")
        
        if user.is_student() and attempt.student_id != user_id:
            raise PermissionException("Access denied")
        elif user.is_teacher() and attempt.quiz.course.teacher_id != user_id:
            raise PermissionException("Access denied")
        
        results = QuizService._get_detailed_results(attempt_id)
        return results
    
    @staticmethod
    def get_quiz_statistics(teacher_id: int, quiz_id: int) -> Dict[str, Any]:
        """Get quiz statistics"""
        quiz = Quiz.query.get(quiz_id)
        if not quiz:
            raise NotFoundException("Quiz not found")
        
        if quiz.course.teacher_id != teacher_id:
            raise PermissionException("Access denied")
        
        attempts = QuizAttempt.query.filter_by(
            quiz_id=quiz_id,
            status='completed'
        ).all()
        
        stats = calculate_quiz_statistics(attempts)
        
        question_stats = []
        for question in quiz.questions:
            correct_count = 0
            total_answers = 0
            
            for attempt in attempts:
                answer = next((a for a in attempt.student_answers if a.question_id == question.id), None)
                if answer:
                    total_answers += 1
                    if answer.is_correct:
                        correct_count += 1
            
            question_stats.append({
                'question_id': question.id,
                'question_text': question.question_text,
                'total_answers': total_answers,
                'correct_answers': correct_count,
                'accuracy_rate': (correct_count / total_answers * 100) if total_answers > 0 else 0
            })
        
        return {
            'quiz': quiz.to_dict(),
            'statistics': stats,
            'question_statistics': question_stats
        }
    
    @staticmethod
    def create_quiz_attempt(quiz_id: int, student_id: int):
        """Create a new quiz attempt"""
        quiz = Quiz.query.get(quiz_id)
        if not quiz:
            raise ValueError("Quiz not found")
        
        existing_attempts = QuizAttempt.query.filter_by(
            quiz_id=quiz_id,
            student_id=student_id
        ).count()
        
        if existing_attempts >= quiz.max_attempts:
            raise ValueError(f"Maximum attempts ({quiz.max_attempts}) reached")
        
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
    def get_quiz_questions(quiz_id: int, include_answers: bool = False):
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
    def submit_quiz_attempt(attempt_id: int, answers: Dict[str, Any]):
        """Submit and grade a quiz attempt"""
        attempt = QuizAttempt.query.get(attempt_id)
        if not attempt:
            raise ValueError("Quiz attempt not found")
        
        if attempt.status != 'in_progress':
            raise ValueError("Quiz has already been submitted")
        
        if attempt.quiz.time_limit_minutes:
            time_spent = calculate_time_spent(attempt.started_at)
            if time_spent > attempt.quiz.time_limit_minutes:
                attempt.status = 'abandoned'
                db.session.commit()
                raise ValueError("Time limit exceeded")
        
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
            
            if question.question_type in ['multiple_choice', 'true_false']:
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
                student_answer.is_correct = None
                student_answer.points_earned = 0
            
            db.session.add(student_answer)
        
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
    def _get_detailed_results(attempt_id: int):
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
                if answer.selected_option:
                    question_data['student_answer'] = answer.selected_option.option_text
                
                correct_options = [opt.option_text for opt in question.answer_options if opt.is_correct]
                question_data['correct_answer'] = correct_options[0] if correct_options else None
                
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
    def get_student_quiz_attempts(student_id: int, quiz_id: int = None):
        """Get all quiz attempts for a student"""
        query = QuizAttempt.query.filter_by(student_id=student_id)
        
        if quiz_id:
            query = query.filter_by(quiz_id=quiz_id)
        
        attempts = query.order_by(QuizAttempt.started_at.desc()).all()
        
        return [attempt.to_dict() for attempt in attempts]
    
    @staticmethod
    def can_retake_quiz(student_id: int, quiz_id: int):
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
        
        in_progress = QuizAttempt.query.filter_by(
            student_id=student_id,
            quiz_id=quiz_id,
            status='in_progress'
        ).first()
        
        if in_progress:
            return False, "You have an in-progress attempt"
        
        return True, f"You have {quiz.max_attempts - attempts} attempts remaining"