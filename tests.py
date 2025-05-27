import pytest
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import (
    User, UserRole, Course, Lesson, Quiz, Question, AnswerOption, 
    QuizAttempt, StudentAnswer, Assignment, AssignmentSubmission, 
    Enrollment, LessonProgress, Achievement, StudentAchievement,
    Certificate, CertificateRequest, Message, Notification,
    NotificationType, NotificationPriority
)

from app.services.auth_service import AuthService
from app.services.course_service import CourseService
from app.services.lesson_service import LessonService
from app.services.quiz_service import QuizService
from app.services.assignment_service import AssignmentService
from app.services.student_service import StudentService
from app.services.teacher_service import TeacherService
from app.services.admin_service import AdminService
from app.services.messaging_service import MessagingService
from app.services.notification_service import NotificationService
from app.services.achievement_service import AchievementService
from app.services.certificate_service import CertificateService

from app.utils.base_controller import ValidationException, PermissionException, NotFoundException

@pytest.fixture(scope='function')
def app():
    """Create test app with in-memory SQLite database"""
    app = create_app('testing')
    
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-secret-key',
        'JWT_SECRET_KEY': 'test-jwt-secret',
        'UPLOAD_FOLDER': '/tmp/test_uploads',
        'MAX_CONTENT_LENGTH': 16 * 1024 * 1024,
    })
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def sample_users(app):
    """Create sample users for testing"""
    with app.app_context():
        users = {}
        
        admin = User(
            username='admin',
            email='admin@test.com',
            full_name='Test Admin',
            role=UserRole.ADMIN,
            is_active=True
        )
        admin.set_password('Admin123!')
        db.session.add(admin)
        
        teacher = User(
            username='teacher',
            email='teacher@test.com',
            full_name='Test Teacher',
            role=UserRole.TEACHER,
            is_active=True
        )
        teacher.set_password('Teacher123!')
        db.session.add(teacher)
        
        student = User(
            username='student',
            email='student@test.com',
            full_name='Test Student',
            role=UserRole.STUDENT,
            is_active=True
        )
        student.set_password('Student123!')
        db.session.add(student)
        
        student2 = User(
            username='student2',
            email='student2@test.com',
            full_name='Test Student 2',
            role=UserRole.STUDENT,
            is_active=True
        )
        student2.set_password('Student123!')
        db.session.add(student2)
        
        db.session.commit()
        
        db.session.refresh(admin)
        db.session.refresh(teacher)
        db.session.refresh(student)
        db.session.refresh(student2)
        
        users = {
            'admin': admin,
            'teacher': teacher,
            'student': student,
            'student2': student2
        }
        
        return users


@pytest.fixture
def sample_course(app, sample_users):
    """Create sample course for testing"""
    with app.app_context():
        course = Course(
            title='Test Course',
            description='A test course for unit testing',
            category='Testing',
            teacher_id=sample_users['teacher'].id,
            is_published=True,
            max_students=50
        )
        db.session.add(course)
        db.session.commit()
        db.session.refresh(course)
        return course


@pytest.fixture
def enrolled_student(app, sample_users, sample_course):
    """Create an enrollment for testing"""
    with app.app_context():
        enrollment = Enrollment(
            student_id=sample_users['student'].id,
            course_id=sample_course.id,
            status='active'
        )
        db.session.add(enrollment)
        db.session.commit()
        return enrollment


class TestAuthService:
    """Test AuthService functionality"""
    
    def test_register_user_success(self, app):
        """Test successful user registration"""
        with app.app_context():
            user_data = {
                'username': 'newuser',
                'email': 'newuser@test.com',
                'password': 'Password123!',
                'full_name': 'New User',
                'role': 'student',
                'age': 25
            }
            
            result = AuthService.register_user(user_data)
            
            assert result['message'] == 'User registered successfully'
            assert result['user']['username'] == 'newuser'
            assert result['user']['email'] == 'newuser@test.com'
            assert result['user']['role'] == 'student'
    
    def test_register_user_missing_required_field(self, app):
        """Test registration with missing required field"""
        with app.app_context():
            user_data = {
                'username': 'newuser',
                'email': 'newuser@test.com',
                'full_name': 'New User',
                'role': 'student'
            }
            
            with pytest.raises(ValidationException) as exc_info:
                AuthService.register_user(user_data)
            
            assert 'password is required' in str(exc_info.value)
    
    def test_register_user_duplicate_username(self, app, sample_users):
        """Test registration with duplicate username"""
        with app.app_context():
            user_data = {
                'username': 'admin',  
                'email': 'newemail@test.com',
                'password': 'Password123!',
                'full_name': 'New User',
                'role': 'student'
            }
            
            with pytest.raises(ValidationException) as exc_info:
                AuthService.register_user(user_data)
            
            assert 'Username already exists' in str(exc_info.value)
    
    def test_register_user_duplicate_email(self, app, sample_users):
        """Test registration with duplicate email"""
        with app.app_context():
            user_data = {
                'username': 'newuser',
                'email': 'admin@test.com',  
                'password': 'Password123!',
                'full_name': 'New User',
                'role': 'student'
            }
            
            with pytest.raises(ValidationException) as exc_info:
                AuthService.register_user(user_data)
            
            assert 'Email already exists' in str(exc_info.value)
    
    def test_login_user_success(self, app, sample_users):
        """Test successful user login"""
        with app.app_context():
            login_data = {
                'username': 'admin',
                'password': 'Admin123!'
            }
            
            result = AuthService.login_user(login_data)
            
            assert result['message'] == 'Login successful'
            assert 'access_token' in result
            assert 'refresh_token' in result
            assert result['user']['username'] == 'admin'
    
    def test_login_user_invalid_credentials(self, app, sample_users):
        """Test login with invalid credentials"""
        with app.app_context():
            login_data = {
                'username': 'admin',
                'password': 'wrongpassword'
            }
            
            with pytest.raises(ValidationException) as exc_info:
                AuthService.login_user(login_data)
            
            assert 'Invalid username or password' in str(exc_info.value)
    
    def test_get_user_profile_success(self, app, sample_users):
        """Test get user profile"""
        with app.app_context():
            result = AuthService.get_user_profile(sample_users['admin'].id)
            
            assert result['username'] == 'admin'
            assert result['email'] == 'admin@test.com'
            assert 'stats' in result
    
    def test_update_user_profile_success(self, app, sample_users):
        """Test update user profile"""
        with app.app_context():
            update_data = {
                'full_name': 'Updated Admin Name',
                'phone': '+1234567890',
                'age': 30
            }
            
            result = AuthService.update_user_profile(sample_users['admin'].id, update_data)
            
            assert result['message'] == 'Profile updated successfully'
            assert result['user']['full_name'] == 'Updated Admin Name'
    
    def test_change_password_success(self, app, sample_users):
        """Test password change"""
        with app.app_context():
            password_data = {
                'current_password': 'Admin123!',
                'new_password': 'NewPassword123!'
            }
            
            result = AuthService.change_password(sample_users['admin'].id, password_data)
            
            assert result['message'] == 'Password changed successfully'


class TestCourseService:
    """Test CourseService functionality"""
    
    def test_create_course_success(self, app, sample_users):
        """Test successful course creation"""
        with app.app_context():
            course_data = {
                'title': 'New Test Course',
                'description': 'A new course for testing',
                'category': 'Programming',
                'max_students': 30,
                'is_published': False
            }
            
            result = CourseService.create_course(sample_users['teacher'].id, course_data)
            
            assert result['message'] == 'Course created successfully'
            assert result['course']['title'] == 'New Test Course'
            assert result['course']['category'] == 'Programming'
    
    def test_create_course_missing_title(self, app, sample_users):
        """Test course creation with missing title"""
        with app.app_context():
            course_data = {
                'description': 'A new course for testing',
                'category': 'Programming'
            }
            
            with pytest.raises(ValidationException) as exc_info:
                CourseService.create_course(sample_users['teacher'].id, course_data)
            
            assert 'title is required' in str(exc_info.value)
    
    def test_get_courses_as_teacher(self, app, sample_users, sample_course):
        """Test get courses as teacher"""
        with app.app_context():
            result = CourseService.get_courses(sample_users['teacher'].id)
            
            assert 'courses' in result
            assert result['total'] >= 1
            assert any(course['title'] == 'Test Course' for course in result['courses'])
    
    def test_get_courses_as_student(self, app, sample_users, sample_course):
        """Test get courses as student (only published)"""
        with app.app_context():
            result = CourseService.get_courses(sample_users['student'].id)
            
            assert 'courses' in result
            for course in result['courses']:
                assert course['is_published'] is True
    
    def test_enroll_student_success(self, app, sample_users, sample_course):
        """Test successful student enrollment"""
        with app.app_context():
            result = CourseService.enroll_student(
                sample_users['student'].id, 
                sample_course.id
            )
            
            assert result['message'] == 'Enrolled in course successfully'
            assert result['enrollment']['student_id'] == sample_users['student'].id
            assert result['enrollment']['course_id'] == sample_course.id
            assert result['enrollment']['status'] == 'active'
    
    def test_enroll_student_duplicate(self, app, sample_users, sample_course):
        """Test duplicate enrollment prevention"""
        with app.app_context():
            CourseService.enroll_student(sample_users['student'].id, sample_course.id)
            
            with pytest.raises(ValidationException) as exc_info:
                CourseService.enroll_student(sample_users['student'].id, sample_course.id)
            
            assert 'Already enrolled' in str(exc_info.value)
    
    def test_drop_course_success(self, app, sample_users, sample_course):
        """Test course dropping"""
        with app.app_context():
            CourseService.enroll_student(sample_users['student'].id, sample_course.id)
            
            result = CourseService.drop_course(sample_users['student'].id, sample_course.id)
            
            assert result['message'] == 'Course dropped successfully'
    
    def test_get_enrolled_courses(self, app, sample_users, sample_course):
        """Test get enrolled courses"""
        with app.app_context():
            CourseService.enroll_student(sample_users['student'].id, sample_course.id)
            
            result = CourseService.get_enrolled_courses(sample_users['student'].id, status='all')
            
            assert 'enrollments' in result
            assert result['total'] >= 1
            assert result['enrollments'][0]['course']['title'] == 'Test Course'

class TestLessonService:
    """Test LessonService functionality"""
    
    def test_create_lesson_success(self, app, sample_users, sample_course):
        """Test successful lesson creation"""
        with app.app_context():
            lesson_data = {
                'course_id': sample_course.id,
                'title': 'Test Lesson',
                'content': 'This is test lesson content',
                'order_number': 1,
                'lesson_type': 'text'
            }
            
            result = LessonService.create_lesson(sample_users['teacher'].id, lesson_data)
            
            assert result['message'] == 'Lesson created successfully'
            assert result['lesson']['title'] == 'Test Lesson'
            assert result['lesson']['order_number'] == 1
    
    def test_create_lesson_video_type(self, app, sample_users, sample_course):
        """Test video lesson creation"""
        with app.app_context():
            lesson_data = {
                'course_id': sample_course.id,
                'title': 'Video Lesson',
                'content': 'Video lesson content',
                'order_number': 1,
                'lesson_type': 'video',
                'video_url': 'https://example.com/video.mp4',
                'duration_minutes': 30
            }
            
            result = LessonService.create_lesson(sample_users['teacher'].id, lesson_data)
            
            assert result['message'] == 'Lesson created successfully'
            assert result['lesson']['lesson_type'] == 'video'
            assert result['lesson']['video_url'] == 'https://example.com/video.mp4'
    
    def test_create_lesson_missing_video_url(self, app, sample_users, sample_course):
        """Test video lesson creation without video URL"""
        with app.app_context():
            lesson_data = {
                'course_id': sample_course.id,
                'title': 'Video Lesson',
                'content': 'Video lesson content',
                'order_number': 1,
                'lesson_type': 'video'
            }
            
            with pytest.raises(ValidationException) as exc_info:
                LessonService.create_lesson(sample_users['teacher'].id, lesson_data)
            
            assert 'Video URL is required' in str(exc_info.value)
    
    def test_get_course_lessons(self, app, sample_users, sample_course, enrolled_student):
        """Test get course lessons"""
        with app.app_context():
            lesson_data = {
                'course_id': sample_course.id,
                'title': 'Test Lesson',
                'content': 'Test content',
                'order_number': 1
            }
            LessonService.create_lesson(sample_users['teacher'].id, lesson_data)
            
            result = LessonService.get_course_lessons(sample_users['student'].id, sample_course.id)
            
            assert 'lessons' in result
            assert result['total'] >= 1
            assert result['lessons'][0]['title'] == 'Test Lesson'
    
    def test_complete_lesson_success(self, app, sample_users, sample_course, enrolled_student):
        """Test lesson completion"""
        with app.app_context():
            lesson_data = {
                'course_id': sample_course.id,
                'title': 'Test Lesson',
                'content': 'Test content',
                'order_number': 1
            }
            lesson_result = LessonService.create_lesson(sample_users['teacher'].id, lesson_data)
            lesson_id = lesson_result['lesson']['id']
            
            result = LessonService.complete_lesson(
                sample_users['student'].id, 
                lesson_id,
                time_spent_minutes=15
            )
            
            assert result['message'] == 'Lesson completed successfully'
            assert result['lesson_completed'] is True
    
    def test_update_lesson_success(self, app, sample_users, sample_course):
        """Test lesson update"""
        with app.app_context():
            lesson_data = {
                'course_id': sample_course.id,
                'title': 'Original Title',
                'content': 'Original content',
                'order_number': 1
            }
            lesson_result = LessonService.create_lesson(sample_users['teacher'].id, lesson_data)
            lesson_id = lesson_result['lesson']['id']
            
            update_data = {
                'title': 'Updated Title',
                'content': 'Updated content'
            }
            
            result = LessonService.update_lesson(sample_users['teacher'].id, lesson_id, update_data)
            
            assert result['message'] == 'Lesson updated successfully'
            assert result['lesson']['title'] == 'Updated Title'


class TestQuizService:
    """Test QuizService functionality"""
    
    def test_create_quiz_success(self, app, sample_users, sample_course):
        """Test successful quiz creation"""
        with app.app_context():
            quiz_data = {
                'course_id': sample_course.id,
                'title': 'Test Quiz',
                'description': 'A test quiz',
                'total_points': 100,
                'passing_score': 70,
                'max_attempts': 3,
                'time_limit_minutes': 60
            }
            
            result = QuizService.create_quiz(sample_users['teacher'].id, quiz_data)
            
            assert result['message'] == 'Quiz created successfully'
            assert result['quiz']['title'] == 'Test Quiz'
            assert result['quiz']['passing_score'] == 70
    
    def test_add_multiple_choice_question(self, app, sample_users, sample_course):
        """Test adding multiple choice question to quiz"""
        with app.app_context():
            quiz_data = {
                'course_id': sample_course.id,
                'title': 'Test Quiz',
                'description': 'A test quiz'
            }
            quiz_result = QuizService.create_quiz(sample_users['teacher'].id, quiz_data)
            quiz_id = quiz_result['quiz']['id']
            
            question_data = {
                'question_text': 'What is 2 + 2?',
                'question_type': 'multiple_choice',
                'points': 10,
                'order_number': 1,
                'options': [
                    {'text': '3', 'is_correct': False},
                    {'text': '4', 'is_correct': True},
                    {'text': '5', 'is_correct': False},
                    {'text': '6', 'is_correct': False}
                ]
            }
            
            result = QuizService.add_question(sample_users['teacher'].id, quiz_id, question_data)
            
            assert result['message'] == 'Question added successfully'
            assert result['question']['question_text'] == 'What is 2 + 2?'
            assert len(result['question']['answer_options']) == 4
    
    def test_add_true_false_question(self, app, sample_users, sample_course):
        """Test adding true/false question to quiz"""
        with app.app_context():
            quiz_data = {
                'course_id': sample_course.id,
                'title': 'Test Quiz'
            }
            quiz_result = QuizService.create_quiz(sample_users['teacher'].id, quiz_data)
            quiz_id = quiz_result['quiz']['id']
            
            question_data = {
                'question_text': 'Python is a programming language.',
                'question_type': 'true_false',
                'points': 5,
                'order_number': 1,
                'options': [
                    {'text': 'True', 'is_correct': True},
                    {'text': 'False', 'is_correct': False}
                ]
            }
            
            result = QuizService.add_question(sample_users['teacher'].id, quiz_id, question_data)
            
            assert result['message'] == 'Question added successfully'
            assert result['question']['question_type'] == 'true_false'
    
    def test_start_quiz_success(self, app, sample_users, sample_course, enrolled_student):
        """Test starting a quiz"""
        with app.app_context():
            quiz_data = {
                'course_id': sample_course.id,
                'title': 'Test Quiz'
            }
            quiz_result = QuizService.create_quiz(sample_users['teacher'].id, quiz_data)
            quiz_id = quiz_result['quiz']['id']
            
            question_data = {
                'question_text': 'Test question?',
                'question_type': 'multiple_choice',
                'points': 10,
                'order_number': 1,
                'options': [
                    {'text': 'Option A', 'is_correct': True},
                    {'text': 'Option B', 'is_correct': False}
                ]
            }
            QuizService.add_question(sample_users['teacher'].id, quiz_id, question_data)
            
            result = QuizService.start_quiz(sample_users['student'].id, quiz_id)
            
            assert 'attempt_id' in result
            assert 'questions' in result
            assert len(result['questions']) >= 1
    
    def test_submit_quiz_success(self, app, sample_users, sample_course, enrolled_student):
        """Test quiz submission"""
        with app.app_context():
            quiz_data = {
                'course_id': sample_course.id,
                'title': 'Test Quiz'
            }
            quiz_result = QuizService.create_quiz(sample_users['teacher'].id, quiz_data)
            quiz_id = quiz_result['quiz']['id']
            
            question_data = {
                'question_text': 'What is 2 + 2?',
                'question_type': 'multiple_choice',
                'points': 10,
                'order_number': 1,
                'options': [
                    {'text': '3', 'is_correct': False},
                    {'text': '4', 'is_correct': True}
                ]
            }
            question_result = QuizService.add_question(sample_users['teacher'].id, quiz_id, question_data)
            question_id = question_result['question']['id']
            
            start_result = QuizService.start_quiz(sample_users['student'].id, quiz_id)
            attempt_id = start_result['attempt_id']
            
            correct_option = next(opt for opt in question_result['question']['answer_options'] if opt['is_correct'])
            
            answers = {str(question_id): correct_option['id']}
            result = QuizService.submit_quiz_with_achievements(
                sample_users['student'].id, 
                attempt_id, 
                answers
            )
            
            assert result['message'] == 'Quiz submitted successfully'
            assert result['result']['score'] == 100.0 


class TestAssignmentService:
    """Test AssignmentService functionality"""
    
    def test_create_assignment_success(self, app, sample_users, sample_course):
        """Test successful assignment creation"""
        with app.app_context():
            assignment_data = {
                'course_id': sample_course.id,
                'title': 'Test Assignment',
                'description': 'Complete this test assignment',
                'total_points': 100,
                'due_date': (datetime.now() + timedelta(days=7)).isoformat()
            }
            
            result = AssignmentService.create_assignment(
                sample_users['teacher'].id, 
                assignment_data
            )
            
            assert result['message'] == 'Assignment created successfully'
            assert result['assignment']['title'] == 'Test Assignment'
            assert result['assignment']['total_points'] == 100
    
    def test_submit_assignment_text_only(self, app, sample_users, sample_course, enrolled_student):
        """Test assignment submission with text only"""
        with app.app_context():
            assignment_data = {
                'course_id': sample_course.id,
                'title': 'Text Assignment',
                'description': 'Submit text only',
                'total_points': 100
            }
            assignment_result = AssignmentService.create_assignment(
                sample_users['teacher'].id, 
                assignment_data
            )
            assignment_id = assignment_result['assignment']['id']
            
            result = AssignmentService.submit_assignment(
                sample_users['student'].id,
                assignment_id,
                'This is my assignment submission text'
            )
            
            assert result['message'] == 'Assignment submitted successfully'
            assert result['submission']['submission_text'] == 'This is my assignment submission text'
            assert result['submission']['status'] == 'submitted'
    
    @patch('app.services.assignment_service.AssignmentService._handle_file_upload')
    def test_submit_assignment_with_file(self, mock_file_upload, app, sample_users, sample_course, enrolled_student):
        """Test assignment submission with file"""
        with app.app_context():
            assignment_data = {
                'course_id': sample_course.id,
                'title': 'File Assignment',
                'description': 'Submit with file',
                'total_points': 100
            }
            assignment_result = AssignmentService.create_assignment(
                sample_users['teacher'].id, 
                assignment_data
            )
            assignment_id = assignment_result['assignment']['id']
            
            mock_file_upload.return_value = '/fake/path/to/file.txt'
            
            mock_file = MagicMock()
            mock_file.filename = 'test.txt'
            
            result = AssignmentService.submit_assignment(
                sample_users['student'].id,
                assignment_id,
                'Assignment with file',
                file=mock_file
            )
            
            assert result['message'] == 'Assignment submitted successfully'
            assert result['submission']['file_path'] == '/fake/path/to/file.txt'
    
    def test_grade_submission_success(self, app, sample_users, sample_course, enrolled_student):
        """Test grading assignment submission"""
        with app.app_context():
            assignment_data = {
                'course_id': sample_course.id,
                'title': 'Gradable Assignment',
                'description': 'Will be graded',
                'total_points': 100
            }
            assignment_result = AssignmentService.create_assignment(
                sample_users['teacher'].id, 
                assignment_data
            )
            assignment_id = assignment_result['assignment']['id']
            
            submit_result = AssignmentService.submit_assignment(
                sample_users['student'].id,
                assignment_id,
                'My submission'
            )
            submission_id = submit_result['submission']['id']
            
            with patch('app.services.notification_service.NotificationService.notify_assignment_graded'):
                result = AssignmentService.grade_submission(
                    sample_users['teacher'].id,
                    submission_id,
                    85.0,
                    'Good work!'
                )
            
            assert result['message'] == 'Assignment graded successfully'
            assert result['submission']['grade'] == 85.0
            assert result['submission']['feedback'] == 'Good work!'
            assert result['submission']['status'] == 'graded'
            
class TestStudentService:
    """Test StudentService functionality"""
    
    def test_get_dashboard_success(self, app, sample_users):
        """Test student dashboard data retrieval"""
        with app.app_context():
            result = StudentService.get_dashboard(sample_users['student'].id)
            
            assert 'stats' in result
            assert 'active_courses' in result
            assert 'recent_activity' in result
            assert 'upcoming_assignments' in result
            assert 'achievements' in result
            assert result['stats']['active_courses'] >= 0
    
    def test_get_progress_success(self, app, sample_users, sample_course, enrolled_student):
        """Test student progress retrieval"""
        with app.app_context():
            result = StudentService.get_progress(sample_users['student'].id)
            
            assert 'courses' in result
            assert 'total_courses' in result
            assert result['total_courses'] >= 1
    
    def test_get_achievements_success(self, app, sample_users):
        """Test student achievements retrieval"""
        with app.app_context():
            AchievementService.create_default_achievements()
            
            result = StudentService.get_achievements(sample_users['student'].id)
            
            assert 'earned' in result
            assert 'available' in result
            assert isinstance(result['earned']['achievements'], list)
    
    def test_get_certificates_success(self, app, sample_users):
        """Test student certificates retrieval"""
        with app.app_context():
            result = StudentService.get_certificates(sample_users['student'].id)
            
            assert 'certificates' in result
            assert 'total' in result
            assert isinstance(result['certificates'], list)
    
    def test_get_study_streak_success(self, app, sample_users):
        """Test study streak calculation"""
        with app.app_context():
            result = StudentService.get_study_streak(sample_users['student'].id)
            
            assert 'current_streak' in result
            assert 'longest_streak' in result
            assert 'last_activity' in result
            assert 'total_study_days' in result
    
    def test_get_course_recommendations_success(self, app, sample_users, sample_course):
        """Test course recommendations"""
        with app.app_context():
            result = StudentService.get_course_recommendations(sample_users['student'].id)
            
            assert 'recommendations' in result
            assert 'total' in result
            assert isinstance(result['recommendations'], list)


class TestTeacherService:
    """Test TeacherService functionality"""
    
    def test_get_dashboard_success(self, app, sample_users, sample_course):
        """Test teacher dashboard data retrieval"""
        with app.app_context():
            result = TeacherService.get_dashboard(sample_users['teacher'].id)
            
            assert 'stats' in result
            assert 'top_courses' in result
            assert 'recent_quiz_attempts' in result
            assert result['stats']['total_courses'] >= 1
    
    def test_get_teacher_courses_success(self, app, sample_users, sample_course):
        """Test teacher courses retrieval"""
        with app.app_context():
            result = TeacherService.get_teacher_courses(sample_users['teacher'].id)
            
            assert 'courses' in result
            assert result['total'] >= 1
            assert any(course['title'] == 'Test Course' for course in result['courses'])
    
    def test_get_course_details_success(self, app, sample_users, sample_course):
        """Test teacher course details"""
        with app.app_context():
            result = TeacherService.get_course_details(sample_users['teacher'].id, sample_course.id)
            
            assert result['title'] == 'Test Course'
            assert 'statistics' in result
            assert 'lessons' in result
            assert 'quizzes' in result
            assert 'assignments' in result
            assert 'students' in result
    
    def test_get_pending_submissions_success(self, app, sample_users):
        """Test pending submissions retrieval"""
        with app.app_context():
            result = TeacherService.get_pending_submissions(sample_users['teacher'].id)
            
            assert 'submissions' in result
            assert 'total' in result
            assert isinstance(result['submissions'], list)
    
    def test_get_individual_student_progress(self, app, sample_users, sample_course, enrolled_student):
        """Test individual student progress"""
        with app.app_context():
            result = TeacherService.get_individual_student_progress(
                sample_users['teacher'].id,
                sample_users['student'].id,
                sample_course.id
            )
            
            assert 'student' in result
            assert 'course' in result
            assert 'progress' in result
            assert result['student']['id'] == sample_users['student'].id
    
    def test_get_student_progress_report(self, app, sample_users, sample_course, enrolled_student):
        """Test student progress report"""
        with app.app_context():
            result = TeacherService.get_student_progress_report(
                sample_users['teacher'].id,
                sample_course.id
            )
            
            assert 'course' in result
            assert 'student_reports' in result
            assert 'total_students' in result
            assert 'summary' in result
            assert result['total_students'] >= 1


class TestAdminService:
    """Test AdminService functionality"""
    
    def test_get_dashboard_success(self, app, sample_users):
        """Test admin dashboard data retrieval"""
        with app.app_context():
            result = AdminService.get_dashboard()
            
            assert 'users' in result
            assert 'courses' in result
            assert 'enrollments' in result
            assert 'quizzes' in result
            assert result['users']['total'] >= 4 
    
    def test_get_users_success(self, app, sample_users):
        """Test admin users retrieval"""
        with app.app_context():
            result = AdminService.get_users()
            
            assert 'users' in result
            assert result['total'] >= 4
            assert len(result['users']) >= 4
    
    def test_get_users_with_filters(self, app, sample_users):
        """Test admin users retrieval with filters"""
        with app.app_context():
            result = AdminService.get_users(role='student')
            
            assert 'users' in result
            for user in result['users']:
                assert user['role'] == 'student'
    
    def test_get_user_details(self, app, sample_users):
        """Test get specific user details"""
        with app.app_context():
            result = AdminService.get_user(sample_users['student'].id)
            
            assert result['username'] == 'student'
            assert result['email'] == 'student@test.com'
            assert 'detailed_stats' in result
    
    def test_update_user_success(self, app, sample_users):
        """Test admin updating user"""
        with app.app_context():
            update_data = {
                'full_name': 'Updated Student Name',
                'age': 25
            }
            
            result = AdminService.update_user(
                sample_users['admin'].id,
                sample_users['student'].id,
                update_data
            )
            
            assert result['message'] == 'User updated successfully'
            assert result['user']['full_name'] == 'Updated Student Name'
    
    def test_toggle_user_active(self, app, sample_users):
        """Test toggling user active status"""
        with app.app_context():
            result = AdminService.toggle_user_active(
                sample_users['admin'].id,
                sample_users['student'].id
            )
            
            assert 'deactivated' in result['message'] or 'activated' in result['message']
    
    def test_get_all_courses_success(self, app, sample_users, sample_course):
        """Test admin courses retrieval"""
        with app.app_context():
            result = AdminService.get_all_courses()
            
            assert 'courses' in result
            assert result['total'] >= 1
            assert any(course['title'] == 'Test Course' for course in result['courses'])
    
    def test_toggle_course_published(self, app, sample_users, sample_course):
        """Test toggling course published status"""
        with app.app_context():
            result = AdminService.toggle_course_published(sample_course.id)
            
            assert 'published' in result['message'] or 'unpublished' in result['message']
    
    def test_get_user_activity_report(self, app, sample_users):
        """Test user activity report"""
        with app.app_context():
            result = AdminService.get_user_activity_report(days=30)
            
            assert 'period_days' in result
            assert 'user_registrations' in result
            assert 'course_enrollments' in result
            assert 'quiz_attempts' in result
    
    def test_get_course_performance_report(self, app, sample_users, sample_course):
        """Test course performance report"""
        with app.app_context():
            result = AdminService.get_course_performance_report()
            
            assert 'courses' in result
            assert 'total_courses' in result
            assert isinstance(result['courses'], list)


class TestMessagingService:
    """Test MessagingService functionality"""
    
    def test_send_message_success(self, app, sample_users, sample_course, enrolled_student):
        """Test successful message sending"""
        with app.app_context():
            message_data = {
                'recipient_id': sample_users['teacher'].id,
                'subject': 'Test Message',
                'content': 'This is a test message from student to teacher',
                'course_id': sample_course.id
            }
            
            result = MessagingService.send_message(sample_users['student'].id, message_data)
            
            assert result['message'] == 'Message sent successfully'
            assert result['message_data']['subject'] == 'Test Message'
            assert result['message_data']['sender_id'] == sample_users['student'].id
    
    def test_send_message_admin_to_anyone(self, app, sample_users):
        """Test admin can message anyone"""
        with app.app_context():
            message_data = {
                'recipient_id': sample_users['student'].id,
                'subject': 'Admin Message',
                'content': 'Message from admin'
            }
            
            result = MessagingService.send_message(sample_users['admin'].id, message_data)
            
            assert result['message'] == 'Message sent successfully'
    
    def test_send_message_permission_denied(self, app, sample_users):
        """Test message permission denial"""
        with app.app_context():
            message_data = {
                'recipient_id': sample_users['teacher'].id,
                'subject': 'Unauthorized Message',
                'content': 'This should fail'
            }
            
            with pytest.raises(PermissionException):
                MessagingService.send_message(sample_users['student2'].id, message_data)
    
    def test_get_messages_success(self, app, sample_users):
        """Test message retrieval"""
        with app.app_context():
            result = MessagingService.get_messages(sample_users['teacher'].id)
            
            assert 'messages' in result
            assert 'total' in result
            assert 'unread_count' in result
            assert isinstance(result['messages'], list)
    
    def test_get_conversations_success(self, app, sample_users):
        """Test conversations retrieval"""
        with app.app_context():
            result = MessagingService.get_conversations(sample_users['teacher'].id)
            
            assert 'conversations' in result
            assert 'total' in result
            assert isinstance(result['conversations'], list)
    
    def test_mark_message_as_read(self, app, sample_users, sample_course, enrolled_student):
        """Test marking message as read"""
        with app.app_context():
            message_data = {
                'recipient_id': sample_users['teacher'].id,
                'subject': 'Read Test',
                'content': 'Mark this as read'
            }
            send_result = MessagingService.send_message(sample_users['student'].id, message_data)
            message_id = send_result['message_data']['id']
            
            result = MessagingService.mark_as_read(sample_users['teacher'].id, message_id)
            
            assert result['message'] == 'Message marked as read'


class TestNotificationService:
    """Test NotificationService functionality"""
    
    def test_create_notification_success(self, app, sample_users):
        """Test notification creation"""
        with app.app_context():
            notification = NotificationService.create_notification(
                recipient_id=sample_users['student'].id,
                notification_type=NotificationType.MESSAGE,
                title='Test Notification',
                message='This is a test notification',
                sender_id=sample_users['teacher'].id,
                priority=NotificationPriority.NORMAL
            )
            
            assert notification.title == 'Test Notification'
            assert notification.recipient_id == sample_users['student'].id
            assert notification.type == NotificationType.MESSAGE.value
    
    def test_get_user_notifications_success(self, app, sample_users):
        """Test user notifications retrieval"""
        with app.app_context():
            NotificationService.create_notification(
                recipient_id=sample_users['student'].id,
                notification_type=NotificationType.MESSAGE,
                title='Test Notification',
                message='Test message'
            )
            
            result = NotificationService.get_user_notifications(sample_users['student'].id)
            
            assert 'notifications' in result
            assert 'total' in result
            assert 'unread_count' in result
            assert result['total'] >= 1
    
    def test_mark_notification_as_read(self, app, sample_users):
        """Test marking notification as read"""
        with app.app_context():
            notification = NotificationService.create_notification(
                recipient_id=sample_users['student'].id,
                notification_type=NotificationType.MESSAGE,
                title='Read Test',
                message='Mark this as read'
            )
            
            result = NotificationService.mark_as_read(sample_users['student'].id, notification.id)
            
            assert result['message'] == 'Notification marked as read'
    
    def test_mark_all_notifications_as_read(self, app, sample_users):
        """Test marking all notifications as read"""
        with app.app_context():
            for i in range(3):
                NotificationService.create_notification(
                    recipient_id=sample_users['student'].id,
                    notification_type=NotificationType.MESSAGE,
                    title=f'Test {i}',
                    message=f'Message {i}'
                )
            
            result = NotificationService.mark_all_as_read(sample_users['student'].id)
            
            assert 'notifications marked as read' in result['message']
    
    def test_delete_notification_success(self, app, sample_users):
        """Test notification deletion"""
        with app.app_context():
            notification = NotificationService.create_notification(
                recipient_id=sample_users['student'].id,
                notification_type=NotificationType.MESSAGE,
                title='Delete Test',
                message='Delete this notification'
            )
            
            result = NotificationService.delete_notification(sample_users['student'].id, notification.id)
            
            assert result['message'] == 'Notification deleted'


class TestAchievementService:
    """Test AchievementService functionality"""
    
    def test_create_default_achievements(self, app):
        """Test default achievements creation"""
        with app.app_context():
            AchievementService.create_default_achievements()
            
            achievements = Achievement.query.all()
            assert len(achievements) > 0
            
            first_steps = Achievement.query.filter_by(name='First Steps').first()
            assert first_steps is not None
            assert first_steps.criteria_type == 'participation'
            
            perfect_score = Achievement.query.filter_by(name='Perfect Score').first()
            assert perfect_score is not None
            assert perfect_score.criteria_type == 'quiz_score'
    
    def test_get_student_achievements_success(self, app, sample_users):
        """Test student achievements retrieval"""
        with app.app_context():
            AchievementService.create_default_achievements()
            
            result = AchievementService.get_student_achievements(sample_users['student'].id)
            
            assert 'achievements' in result
            assert 'total_achievements' in result
            assert 'total_points' in result
            assert isinstance(result['achievements'], list)
    
    def test_get_available_achievements(self, app, sample_users):
        """Test available achievements retrieval"""
        with app.app_context():
            AchievementService.create_default_achievements()
            
            result = AchievementService.get_available_achievements(sample_users['student'].id)
            
            assert 'available_achievements' in result
            assert 'total_available' in result
            assert isinstance(result['available_achievements'], list)
    
    def test_award_achievement_success(self, app, sample_users):
        """Test manual achievement awarding"""
        with app.app_context():
            AchievementService.create_default_achievements()
            achievement = Achievement.query.filter_by(name='First Steps').first()
            
            result = AchievementService.award_achievement(
                sample_users['student'].id,
                achievement.id
            )
            
            assert result['message'] == 'Achievement awarded successfully'
            assert result['achievement']['name'] == 'First Steps'
    
    def test_check_quiz_achievement(self, app, sample_users, sample_course, enrolled_student):
        """Test quiz achievement checking"""
        with app.app_context():
            AchievementService.create_default_achievements()
            
            quiz_data = {'course_id': sample_course.id, 'title': 'Achievement Quiz'}
            quiz_result = QuizService.create_quiz(sample_users['teacher'].id, quiz_data)
            quiz_id = quiz_result['quiz']['id']
            
            attempt = QuizAttempt(
                quiz_id=quiz_id,
                student_id=sample_users['student'].id,
                attempt_number=1,
                score=100.0,
                status='completed'
            )
            db.session.add(attempt)
            db.session.commit()
            
            achievements = AchievementService.check_quiz_achievement(
                sample_users['student'].id,
                attempt.id
            )
            
            assert isinstance(achievements, list)


class TestCertificateService:
    """Test CertificateService functionality"""
    
    def test_get_student_certificates_success(self, app, sample_users):
        """Test student certificates retrieval"""
        with app.app_context():
            result = CertificateService.get_student_certificates(sample_users['student'].id)
            
            assert isinstance(result, list)
    
    def test_request_certificate_approval_not_completed(self, app, sample_users, sample_course):
        """Test certificate request for incomplete course"""
        with app.app_context():
            CourseService.enroll_student(sample_users['student'].id, sample_course.id)
            
            with pytest.raises(ValidationException) as exc_info:
                CertificateService.request_certificate_approval(
                    sample_users['student'].id,
                    sample_course.id
                )
            
            assert 'must be completed' in str(exc_info.value)
    
    def test_request_certificate_approval_success(self, app, sample_users, sample_course):
        """Test successful certificate request"""
        with app.app_context():
            enrollment = Enrollment(
                student_id=sample_users['student'].id,
                course_id=sample_course.id,
                status='completed',
                progress_percentage=100.0,
                completed_at=datetime.now()
            )
            db.session.add(enrollment)
            db.session.commit()
            
            result = CertificateService.request_certificate_approval(
                sample_users['student'].id,
                sample_course.id
            )
            
            assert 'successfully' in result['message'].lower() or 'submitted' in result['message'].lower()
            
    def test_get_pending_certificates(self, app, sample_users):
        """Test get pending certificates (admin only)"""
        with app.app_context():
            result = CertificateService.get_pending_certificates(sample_users['admin'].id)
            
            assert 'pending_certificates' in result
            assert 'total' in result
            assert isinstance(result['pending_certificates'], list)
    
    def test_get_certificate_requests(self, app, sample_users):
        """Test get certificate requests (admin only)"""
        with app.app_context():
            result = CertificateService.get_certificate_requests(sample_users['admin'].id)
            
            assert 'pending_requests' in result
            assert 'recent_reviewed' in result
            assert 'stats' in result
    
    def test_verify_certificate_not_found(self, app):
        """Test certificate verification with invalid code"""
        with app.app_context():
            with pytest.raises(NotFoundException):
                CertificateService.verify_certificate('INVALID_CODE')


def run_specific_test_class(test_class_name):
    """Run a specific test class"""
    print(f"\n🧪 Running {test_class_name} tests...")
    
    test_classes = {
        'auth': 'TestAuthService',
        'course': 'TestCourseService',
        'lesson': 'TestLessonService',
        'quiz': 'TestQuizService',
        'assignment': 'TestAssignmentService',
        'student': 'TestStudentService',
        'teacher': 'TestTeacherService',
        'admin': 'TestAdminService',
        'messaging': 'TestMessagingService',
        'notification': 'TestNotificationService',
        'achievement': 'TestAchievementService',
        'certificate': 'TestCertificateService'
    }
    
    if test_class_name.lower() in test_classes:
        pytest.main(['-v', '-k', test_classes[test_class_name.lower()], __file__])
    else:
        print(f"❌ Unknown test class: {test_class_name}")
        print(f"Available classes: {', '.join(test_classes.keys())}")


def main():
    """Main function to run tests"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run LMS Service Tests')
    parser.add_argument('--service', '-s', type=str, help='Run tests for specific service')
    parser.add_argument('--coverage', '-c', action='store_true', help='Run with coverage report')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--failfast', '-x', action='store_true', help='Stop on first failure')
    
    args = parser.parse_args()
    
    pytest_args = []
    
    if args.verbose:
        pytest_args.append('-v')
    
    if args.failfast:
        pytest_args.append('-x')
    
    if args.coverage:
        pytest_args.extend([
            '--cov=app.services',
            '--cov-report=html',
            '--cov-report=term-missing',
            '--cov-fail-under=80'
        ])
    
    if args.service:
        run_specific_test_class(args.service)
        return
    
    print("🚀 Running LMS Services Test Suite...")
    print("=" * 50)
    
    pytest_args.append(__file__)
    
    exit_code = pytest.main(pytest_args)
    
    if exit_code == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ Some tests failed. Exit code: {exit_code}")
    
    return exit_code


if __name__ == '__main__':
    main()
            