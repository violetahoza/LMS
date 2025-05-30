"""
Learning Management System Models

This module contains all the database models for the LMS application,
including User, Course, Lesson, Quiz, Assignment, and related models.
Each model represents a database table and includes methods for
data manipulation and serialization.

"""

from app import db 
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import enum

class UserRole(enum.Enum):
    """Enumeration for user roles in the system."""
    ADMIN = 'admin'
    TEACHER = 'teacher'
    STUDENT = 'student'

class User(UserMixin, db.Model):
    """User model representing all system users."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.Enum(UserRole), nullable=False)
    phone = db.Column(db.String(20))
    age = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    is_active = db.Column(db.Boolean, default=True)
    
    taught_courses = db.relationship('Course', backref='teacher', lazy='dynamic', foreign_keys='Course.teacher_id')
    enrollments = db.relationship('Enrollment', backref='student', lazy='dynamic', foreign_keys='Enrollment.student_id')
    quiz_attempts = db.relationship('QuizAttempt', backref='student', lazy='dynamic')
    assignment_submissions = db.relationship('AssignmentSubmission', backref='student', lazy='dynamic', foreign_keys='AssignmentSubmission.student_id')
    achievements = db.relationship('StudentAchievement', backref='student', lazy='dynamic')
    
    
    def set_password(self, password):
        """Hash and set the user's password."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify a password against the stored hash."""
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        """Check if the user has admin privileges."""
        return self.role == UserRole.ADMIN
    
    def is_teacher(self):
        """Check if the user is a teacher."""
        return self.role == UserRole.TEACHER
    
    def is_student(self):
        """Check if the user is a student."""
        return self.role == UserRole.STUDENT
    
    def can_access_course(self, course):
        """Check if user can access a specific course.
        Permission logic:
        - Admins: Can access all courses
        - Teachers: Can access courses they teach
        - Students: Can access courses they're enrolled in (active or completed)
        """
        if self.is_admin():
            return True
        
        if self.is_teacher():
            return course.teacher_id == self.id
        
        if self.is_student():
            enrollment = Enrollment.query.filter_by(
                student_id=self.id,
                course_id=course.id
            ).filter(Enrollment.status.in_(['active', 'completed'])).first()
            return enrollment is not None
        
        return False
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role.value,
            'phone': self.phone,
            'age': self.age,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active
        }

class Course(db.Model):
    """Courses are created by teachers and can be enrolled in by students.
    Each course contains lessons, quizzes, assignments, and tracks student progress.
    """
    __tablename__ = 'courses'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(100))
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    max_students = db.Column(db.Integer, default=50)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    is_published = db.Column(db.Boolean, default=False)
    
    lessons = db.relationship('Lesson', backref='course', lazy='dynamic', cascade='all, delete-orphan')
    enrollments = db.relationship('Enrollment', backref='course', lazy='dynamic', cascade='all, delete-orphan')
    quizzes = db.relationship('Quiz', backref='course', lazy='dynamic', cascade='all, delete-orphan')
    assignments = db.relationship('Assignment', backref='course', lazy='dynamic', cascade='all, delete-orphan')
    certificates = db.relationship('Certificate', backref='course', lazy='dynamic', cascade='all, delete-orphan')
    
    def get_enrollment_count(self):
        """Get the number of currently enrolled students."""
        return self.enrollments.filter_by(status='active').count()
    
    def is_full(self):
        """Check if course has reached maximum enrollment capacity."""
        return self.get_enrollment_count() >= self.max_students
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'teacher_id': self.teacher_id,
            'teacher_name': self.teacher.full_name if self.teacher else None,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'max_students': self.max_students,
            'current_students': self.get_enrollment_count(),
            'is_published': self.is_published,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Lesson(db.Model):
    """Lessons are part of a course and can contain various types of content (video, text or mixed content)."""
    __tablename__ = 'lessons'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    order_number = db.Column(db.Integer, nullable=False)
    lesson_type = db.Column(db.Enum('video', 'text', 'mixed'), default='text')
    video_url = db.Column(db.String(500))
    duration_minutes = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    progress_records = db.relationship('LessonProgress', backref='lesson', lazy='dynamic', cascade='all, delete-orphan')
    quizzes = db.relationship('Quiz', backref='lesson', lazy='dynamic')
    assignments = db.relationship('Assignment', backref='lesson', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'course_id': self.course_id,
            'title': self.title,
            'content': self.content,
            'order_number': self.order_number,
            'lesson_type': self.lesson_type,
            'video_url': self.video_url,
            'duration_minutes': self.duration_minutes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Enrollment(db.Model):
    """Student enrollment in a course. Tracks a student's participation in a course, including progress,
    completion status, and enrollment timeline.
    """
    __tablename__ = 'enrollments'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.now)
    completed_at = db.Column(db.DateTime)
    status = db.Column(db.Enum('active', 'completed', 'dropped'), default='active')
    progress_percentage = db.Column(db.Float, default=0.0)
    
    __table_args__ = (db.UniqueConstraint('student_id', 'course_id'),)
    
    def calculate_progress(self):
        """Calculate overall course progress percentage.
        Progress is calculated based on:
        - Completed lessons
        - Passed quizzes (meeting passing score)
        - Submitted assignments
        """
        course = self.course
        total_components = 0
        completed_components = 0
        
        from app.models import QuizAttempt, AssignmentSubmission, LessonProgress, Lesson
        
        total_lessons = course.lessons.count()
        if total_lessons > 0:
            completed_lessons = LessonProgress.query.filter_by(
                student_id=self.student_id
            ).join(Lesson).filter(
                Lesson.course_id == course.id,
                LessonProgress.completed_at.isnot(None)
            ).count()
            
            total_components += total_lessons
            completed_components += completed_lessons
        
        course_quizzes = course.quizzes.all()
        for quiz in course_quizzes:
            total_components += 1
            
            best_attempt = QuizAttempt.query.filter_by(
                student_id=self.student_id,
                quiz_id=quiz.id,
                status='completed'
            ).order_by(QuizAttempt.score.desc()).first()
            
            if best_attempt and best_attempt.score is not None and best_attempt.score >= quiz.passing_score:
                completed_components += 1
        
        course_assignments = course.assignments.all()
        for assignment in course_assignments:
            total_components += 1
            
            submission = AssignmentSubmission.query.filter_by(
                student_id=self.student_id,
                assignment_id=assignment.id
            ).first()
            
            if submission and submission.status in ['submitted', 'graded']:
                completed_components += 1
        
        if total_components == 0:
            return 100.0  
        
        progress = (completed_components / total_components) * 100
        return min(round(progress, 2), 100.0)

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'course_id': self.course_id,
            'course_title': self.course.title if self.course else None,
            'enrolled_at': self.enrolled_at.isoformat() if self.enrolled_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status,
            'progress_percentage': self.progress_percentage
        }

class Quiz(db.Model):
    """Quizzes are assessments within a course that test student knowledge.
    Each quiz can have multiple questions and tracks student attempts and scores.
    """
    __tablename__ = 'quizzes'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lessons.id'))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    total_points = db.Column(db.Integer, default=100)
    passing_score = db.Column(db.Integer, default=60)
    time_limit_minutes = db.Column(db.Integer)
    max_attempts = db.Column(db.Integer, default=3)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    questions = db.relationship('Question', backref='quiz', lazy='dynamic', cascade='all, delete-orphan')
    attempts = db.relationship('QuizAttempt', backref='quiz', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'course_id': self.course_id,
            'lesson_id': self.lesson_id,
            'title': self.title,
            'description': self.description,
            'total_points': self.total_points,
            'passing_score': self.passing_score,
            'time_limit_minutes': self.time_limit_minutes,
            'max_attempts': self.max_attempts,
            'question_count': self.questions.count(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Question(db.Model):
    """Questions are part of a quiz and can be of various types (multiple choice, true/false, short answer)."""
    __tablename__ = 'questions'
    
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.Enum('multiple_choice', 'true_false', 'short_answer'), nullable=False)
    points = db.Column(db.Integer, default=10)
    order_number = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    answer_options = db.relationship('AnswerOption', backref='question', lazy='dynamic', cascade='all, delete-orphan')
    student_answers = db.relationship('StudentAnswer', backref='question', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'quiz_id': self.quiz_id,
            'question_text': self.question_text,
            'question_type': self.question_type,
            'points': self.points,
            'order_number': self.order_number,
            'answer_options': [opt.to_dict() for opt in self.answer_options]
        }

class AnswerOption(db.Model):
    """Answer options for multiple choice questions in quizzes."""
    __tablename__ = 'answer_options'
    
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    option_text = db.Column(db.String(500), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'option_text': self.option_text,
            'is_correct': self.is_correct
        }

class QuizAttempt(db.Model):
    """Quiz attempts by students. Tracks each attempt, including score, time spent, and status."""
    __tablename__ = 'quiz_attempts'
    
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    attempt_number = db.Column(db.Integer, nullable=False)
    score = db.Column(db.Float)
    started_at = db.Column(db.DateTime, default=datetime.now)
    submitted_at = db.Column(db.DateTime)
    time_spent_minutes = db.Column(db.Integer)
    status = db.Column(db.Enum('in_progress', 'completed', 'abandoned'), default='in_progress')
    graded_at = db.Column(db.DateTime, nullable=True)
    student_answers = db.relationship('StudentAnswer', backref='attempt', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'quiz_id': self.quiz_id,
            'student_id': self.student_id,
            'attempt_number': self.attempt_number,
            'score': self.score,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'graded_at': self.graded_at.isoformat() if self.graded_at else None,  
            'time_spent_minutes': self.time_spent_minutes,
            'status': self.status
        }

class StudentAnswer(db.Model):
    """Student answers to quiz questions. Tracks the answer text, selected options, correctness, and points earned."""
    __tablename__ = 'student_answers'
    
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    answer_text = db.Column(db.Text)
    selected_option_id = db.Column(db.Integer, db.ForeignKey('answer_options.id'))
    is_correct = db.Column(db.Boolean)
    points_earned = db.Column(db.Float, default=0)
    
    selected_option = db.relationship('AnswerOption', foreign_keys=[selected_option_id])

class Assignment(db.Model):
    """Assignments are tasks given to students within a course.
    Each assignment can have a title, description, due date, and total points.
    Students can submit assignments, and teachers can grade them.
    """
    __tablename__ = 'assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lessons.id'))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime)
    total_points = db.Column(db.Integer, default=100)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    submissions = db.relationship('AssignmentSubmission', backref='assignment', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'course_id': self.course_id,
            'lesson_id': self.lesson_id,
            'title': self.title,
            'description': self.description,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'total_points': self.total_points,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class AssignmentSubmission(db.Model):
    """Assignment submissions by students. Tracks submission text, file uploads, grading status, and feedback."""
    __tablename__ = 'assignment_submissions'
    
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    submission_text = db.Column(db.Text)
    file_path = db.Column(db.String(500))
    submitted_at = db.Column(db.DateTime, default=datetime.now)
    grade = db.Column(db.Float)
    feedback = db.Column(db.Text)
    graded_at = db.Column(db.DateTime)
    graded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.Enum('submitted', 'graded', 'returned'), default='submitted')
    
    __table_args__ = (db.UniqueConstraint('assignment_id', 'student_id'),)
    
    grader = db.relationship('User', foreign_keys=[graded_by])
    
    def to_dict(self):
        return {
            'id': self.id,
            'assignment_id': self.assignment_id,
            'student_id': self.student_id,
            'submission_text': self.submission_text,
            'file_path': self.file_path,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'grade': self.grade,
            'feedback': self.feedback,
            'graded_at': self.graded_at.isoformat() if self.graded_at else None,
            'graded_by': self.graded_by,
            'status': self.status
        }

class LessonProgress(db.Model):
    """Tracks student progress on lessons, including viewing status, completion time, and time spent."""
    __tablename__ = 'lesson_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lessons.id'), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.now)
    completed_at = db.Column(db.DateTime)
    time_spent_minutes = db.Column(db.Integer, default=0)
    
    __table_args__ = (db.UniqueConstraint('student_id', 'lesson_id'),)
    
    student = db.relationship('User', backref='lesson_progress')

class Achievement(db.Model):
    """Achievements are rewards given to students for completing certain criteria in courses.
    Each achievement has a name, description, badge icon, points value, and criteria type."""
    __tablename__ = 'achievements'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    badge_icon = db.Column(db.String(255))
    points_value = db.Column(db.Integer, default=0)
    criteria_type = db.Column(db.Enum('course_completion', 'quiz_score', 'streak', 'participation'), nullable=False)
    criteria_value = db.Column(db.Integer)
    
    student_achievements = db.relationship('StudentAchievement', backref='achievement', lazy='dynamic')

class StudentAchievement(db.Model):
    """Tracks achievements earned by students."""
    __tablename__ = 'student_achievements'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievements.id'), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.now)
    
    __table_args__ = (db.UniqueConstraint('student_id', 'achievement_id'),)

class Certificate(db.Model):
    """Certificates are issued to students upon successful completion of a course.
    Each certificate has a unique code, student ID, course ID, and issue date."""
    __tablename__ = 'certificates'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    certificate_code = db.Column(db.String(100), unique=True, nullable=False)
    issued_at = db.Column(db.DateTime, default=datetime.now)
    
    __table_args__ = (db.UniqueConstraint('student_id', 'course_id'),)
    
    student = db.relationship('User', backref='certificates')
    
    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'course_id': self.course_id,
            'course_title': self.course.title if self.course else None,
            'student_name': self.student.full_name if self.student else None,
            'certificate_code': self.certificate_code,
            'issued_at': self.issued_at.isoformat() if self.issued_at else None
        }
    
class Message(db.Model):
    """Message model for communication between users"""
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True)
    subject = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    is_announcement = db.Column(db.Boolean, default=False, nullable=False)
    
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_messages')
    course = db.relationship('Course', backref='messages')
    
    def to_dict(self):
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'recipient_id': self.recipient_id,
            'course_id': self.course_id,
            'subject': self.subject,
            'content': self.content,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'is_announcement': self.is_announcement,
            'sender_name': self.sender.full_name if self.sender else None,
            'recipient_name': self.recipient.full_name if self.recipient else None
        }
    
class NotificationType(enum.Enum):
    """Enumeration for different types of notifications in the LMS."""
    MESSAGE = 'message'
    ENROLLMENT = 'enrollment'
    ASSIGNMENT_SUBMISSION = 'assignment_submission'
    ASSIGNMENT_GRADED = 'assignment_graded'
    QUIZ_SUBMISSION = 'quiz_submission'
    QUIZ_GRADED = 'quiz_graded'
    COURSE_COMPLETION = 'course_completion'
    NEW_CONTENT = 'new_content'
    CERTIFICATE_ISSUED = 'certificate_issued'
    CERTIFICATE_REQUEST = 'certificate_request'
    CERTIFICATE_APPROVED = 'certificate_approved'
    CERTIFICATE_REJECTED = 'certificate_rejected'
    USER_REGISTRATION = 'user_registration' 
    COURSE_PUBLISHED = 'course_published'  
    ACHIEVEMENT_EARNED = 'achievement_earned'

class NotificationPriority(enum.Enum):
    """Enumeration for notification priority levels."""
    LOW = 'low'
    NORMAL = 'normal'
    HIGH = 'high'
    URGENT = 'urgent'

class Notification(db.Model):
    """Notification model for user notifications"""
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    type = db.Column(db.String(40), nullable=False)
    priority = db.Column(db.String(30), default='normal')
    
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    action_url = db.Column(db.String(500), nullable=True)
    related_id = db.Column(db.Integer, nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_notifications')
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_notifications')
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.now()
            db.session.commit()
    
    def to_dict(self):
        return {
            'id': self.id,
            'recipient_id': self.recipient_id,
            'sender_id': self.sender_id,
            'type': self.type,
            'priority': self.priority,
            'title': self.title,
            'message': self.message,
            'action_url': self.action_url,
            'related_id': self.related_id,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'sender_name': self.sender.full_name if self.sender else None,
            'recipient_name': self.recipient.full_name if self.recipient else None
        }
class CertificateRequest(db.Model):
    """Certificate request model for students to request course completion certificates.
    Admins can review and approve or reject requests."""
    __tablename__ = 'certificate_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    requested_at = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.Enum('pending', 'approved', 'rejected'), default='pending')
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    reviewed_at = db.Column(db.DateTime)
    rejection_reason = db.Column(db.Text)
    
    student = db.relationship('User', foreign_keys=[student_id], backref='certificate_requests')
    course = db.relationship('Course', backref='certificate_requests')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])
    
    __table_args__ = (db.UniqueConstraint('student_id', 'course_id'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'course_id': self.course_id,
            'student_name': self.student.full_name if self.student else None,
            'course_title': self.course.title if self.course else None,
            'requested_at': self.requested_at.isoformat() if self.requested_at else None,
            'status': self.status,
            'reviewed_by': self.reviewed_by,
            'reviewer_name': self.reviewer.full_name if self.reviewer else None,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'rejection_reason': self.rejection_reason
        }