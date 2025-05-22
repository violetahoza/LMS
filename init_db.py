import os
import sys
from datetime import datetime, date, timedelta
import random
import string
from flask import Flask
from flask_migrate import Migrate
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
import pymysql
from dotenv import load_dotenv

# Add the project directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.models import db, User, UserRole, Course, Lesson, Enrollment, Quiz, Question, AnswerOption, Assignment, Achievement
from config import config

# Load environment variables
load_dotenv()

def create_database():
    """Create the database if it doesn't exist"""
    db_name = os.environ.get('DB_NAME')
    db_user = os.environ.get('DB_USER')
    db_password = os.environ.get('DB_PASSWORD')
    db_host = os.environ.get('DB_HOST')
    db_port = os.environ.get('DB_PORT')
    
    # Connect to MySQL server without specifying a database
    connection_string = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}"
    engine = create_engine(connection_string)
    
    try:
        # Create database if it doesn't exist
        with engine.connect() as conn:
            conn.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
            conn.commit()
        print(f"Database '{db_name}' created or already exists.")
    except Exception as e:
        print(f"Error creating database: {e}")
        return False
    finally:
        engine.dispose()
    
    return True

def init_database(app):
    """Initialize the database with tables and sample data"""
    with app.app_context():
        # Create all tables
        db.create_all()
        print("All tables created successfully!")
        
        # Check if data already exists
        if User.query.first():
            print("Database already contains data. Skipping initialization.")
            return
        
        # Create sample users
        print("Creating sample users...")
        
        # Admin user
        admin = User(
            username='admin',
            email='admin@lms.com',
            full_name='System Administrator',
            role=UserRole.ADMIN,
            phone='555-0001',
            age=35
        )
        admin.set_password('admin123')
        db.session.add(admin)
        
        # Teacher users
        teachers = []
        teacher_data = [
            ('john_smith', 'john.smith@lms.com', 'John Smith', '555-0002', 42),
            ('sarah_jones', 'sarah.jones@lms.com', 'Sarah Jones', '555-0003', 38),
            ('mike_wilson', 'mike.wilson@lms.com', 'Mike Wilson', '555-0004', 45),
            ('emily_brown', 'emily.brown@lms.com', 'Emily Brown', '555-0005', 36),
            ('david_lee', 'david.lee@lms.com', 'David Lee', '555-0006', 40)
        ]
        
        for username, email, full_name, phone, age in teacher_data:
            teacher = User(
                username=username,
                email=email,
                full_name=full_name,
                role=UserRole.TEACHER,
                phone=phone,
                age=age
            )
            teacher.set_password('teacher123')
            teachers.append(teacher)
            db.session.add(teacher)
        
        # Student users
        students = []
        student_data = [
            ('alice_martin', 'alice.martin@student.com', 'Alice Martin', '555-1001', 22),
            ('bob_davis', 'bob.davis@student.com', 'Bob Davis', '555-1002', 24),
            ('emma_miller', 'emma.miller@student.com', 'Emma Miller', '555-1003', 21),
            ('david_garcia', 'david.garcia@student.com', 'David Garcia', '555-1004', 23),
            ('lisa_martinez', 'lisa.martinez@student.com', 'Lisa Martinez', '555-1005', 25),
            ('james_wilson', 'james.wilson@student.com', 'James Wilson', '555-1006', 22),
            ('sophia_anderson', 'sophia.anderson@student.com', 'Sophia Anderson', '555-1007', 24),
            ('oliver_taylor', 'oliver.taylor@student.com', 'Oliver Taylor', '555-1008', 23),
            ('isabella_thomas', 'isabella.thomas@student.com', 'Isabella Thomas', '555-1009', 21),
            ('ethan_jackson', 'ethan.jackson@student.com', 'Ethan Jackson', '555-1010', 25)
        ]
        
        for username, email, full_name, phone, age in student_data:
            student = User(
                username=username,
                email=email,
                full_name=full_name,
                role=UserRole.STUDENT,
                phone=phone,
                age=age
            )
            student.set_password('student123')
            students.append(student)
            db.session.add(student)
        
        db.session.commit()
        print(f"Created {len(teachers)} teachers and {len(students)} students")
        
        # Create sample courses
        print("Creating sample courses...")
        courses = []
        course_data = [
            {
                'title': 'Introduction to Python Programming',
                'description': 'Learn Python from scratch with hands-on projects and real-world applications.',
                'category': 'Programming',
                'teacher': teachers[0],
                'start_date': date.today(),
                'end_date': date.today() + timedelta(days=90),
                'is_published': True
            },
            {
                'title': 'Web Development with Flask',
                'description': 'Master web development using Flask framework and build dynamic web applications.',
                'category': 'Web Development',
                'teacher': teachers[0],
                'start_date': date.today() + timedelta(days=7),
                'end_date': date.today() + timedelta(days=97),
                'is_published': True
            },
            {
                'title': 'Data Science Fundamentals',
                'description': 'Explore data analysis, visualization, and machine learning basics.',
                'category': 'Data Science',
                'teacher': teachers[1],
                'start_date': date.today(),
                'end_date': date.today() + timedelta(days=120),
                'is_published': True
            },
            {
                'title': 'Database Design and SQL',
                'description': 'Learn to design efficient databases and write complex SQL queries.',
                'category': 'Database',
                'teacher': teachers[2],
                'start_date': date.today() - timedelta(days=30),
                'end_date': date.today() + timedelta(days=60),
                'is_published': True
            },
            {
                'title': 'JavaScript for Beginners',
                'description': 'Start your journey with JavaScript and build interactive web applications.',
                'category': 'Programming',
                'teacher': teachers[3],
                'start_date': date.today() + timedelta(days=14),
                'end_date': date.today() + timedelta(days=104),
                'is_published': True
            },
            {
                'title': 'Machine Learning Basics',
                'description': 'Introduction to machine learning algorithms and their applications.',
                'category': 'AI/ML',
                'teacher': teachers[1],
                'start_date': date.today() + timedelta(days=30),
                'end_date': date.today() + timedelta(days=150),
                'is_published': False
            }
        ]
        
        for course_info in course_data:
            course = Course(**course_info)
            courses.append(course)
            db.session.add(course)
        
        db.session.commit()
        print(f"Created {len(courses)} courses")
        
        # Create lessons for each course
        print("Creating lessons...")
        lesson_count = 0
        for course in courses[:5]:  # Create lessons for published courses
            num_lessons = random.randint(5, 10)
            for i in range(num_lessons):
                lesson = Lesson(
                    course_id=course.id,
                    title=f"Lesson {i+1}: {course.title} - Topic {i+1}",
                    content=f"This is the content for lesson {i+1} of {course.title}. It covers important concepts and includes practical examples.",
                    order_number=i+1,
                    lesson_type=random.choice(['text', 'video', 'mixed']),
                    video_url=f"https://example.com/videos/{course.id}/lesson{i+1}.mp4" if random.choice([True, False]) else None,
                    duration_minutes=random.randint(15, 60)
                )
                db.session.add(lesson)
                lesson_count += 1
        
        db.session.commit()
        print(f"Created {lesson_count} lessons")
        
        # Create enrollments
        print("Creating enrollments...")
        enrollment_count = 0
        for student in students:
            # Each student enrolls in 2-4 courses
            num_courses = random.randint(2, 4)
            enrolled_courses = random.sample(courses[:5], min(num_courses, 5))
            
            for course in enrolled_courses:
                enrollment = Enrollment(
                    student_id=student.id,
                    course_id=course.id,
                    status='active',
                    progress_percentage=random.uniform(0, 80)
                )
                db.session.add(enrollment)
                enrollment_count += 1
        
        db.session.commit()
        print(f"Created {enrollment_count} enrollments")
        
        # Create quizzes with questions
        print("Creating quizzes and questions...")
        quiz_count = 0
        question_count = 0
        
        for course in courses[:4]:  # Create quizzes for first 4 courses
            lessons = course.lessons.all()
            
            # Create 1-2 quizzes per course
            for i in range(random.randint(1, 2)):
                quiz = Quiz(
                    course_id=course.id,
                    lesson_id=random.choice(lessons).id if lessons else None,
                    title=f"Quiz {i+1}: {course.title}",
                    description=f"Test your knowledge of {course.title}",
                    total_points=100,
                    passing_score=60,
                    time_limit_minutes=30,
                    max_attempts=3
                )
                db.session.add(quiz)
                db.session.flush()  # Get quiz.id
                quiz_count += 1
                
                # Create 5-10 questions per quiz
                for j in range(random.randint(5, 10)):
                    question_type = random.choice(['multiple_choice', 'true_false'])
                    question = Question(
                        quiz_id=quiz.id,
                        question_text=f"Question {j+1}: Sample question about {course.title}?",
                        question_type=question_type,
                        points=10,
                        order_number=j+1
                    )
                    db.session.add(question)
                    db.session.flush()  # Get question.id
                    question_count += 1
                    
                    # Create answer options
                    if question_type == 'multiple_choice':
                        correct_index = random.randint(0, 3)
                        for k in range(4):
                            option = AnswerOption(
                                question_id=question.id,
                                option_text=f"Option {k+1}",
                                is_correct=(k == correct_index)
                            )
                            db.session.add(option)
                    else:  # true_false
                        true_option = AnswerOption(
                            question_id=question.id,
                            option_text="True",
                            is_correct=random.choice([True, False])
                        )
                        false_option = AnswerOption(
                            question_id=question.id,
                            option_text="False",
                            is_correct=not true_option.is_correct
                        )
                        db.session.add(true_option)
                        db.session.add(false_option)
        
        db.session.commit()
        print(f"Created {quiz_count} quizzes with {question_count} questions")
        
        # Create assignments
        print("Creating assignments...")
        assignment_count = 0
        for course in courses[:4]:
            lessons = course.lessons.all()
            
            # Create 2-3 assignments per course
            for i in range(random.randint(2, 3)):
                assignment = Assignment(
                    course_id=course.id,
                    lesson_id=random.choice(lessons).id if lessons and random.choice([True, False]) else None,
                    title=f"Assignment {i+1}: {course.title}",
                    description=f"Complete this assignment to demonstrate your understanding of {course.title}",
                    due_date=datetime.now() + timedelta(days=random.randint(7, 30)),
                    total_points=100
                )
                db.session.add(assignment)
                assignment_count += 1
        
        db.session.commit()
        print(f"Created {assignment_count} assignments")
        
        # Create achievements
        print("Creating achievements...")
        achievements_data = [
            {
                'name': 'First Steps',
                'description': 'Complete your first lesson',
                'badge_icon': 'first-steps.png',
                'points_value': 10,
                'criteria_type': 'participation',
                'criteria_value': 1
            },
            {
                'name': 'Quiz Master',
                'description': 'Score 90% or higher on a quiz',
                'badge_icon': 'quiz-master.png',
                'points_value': 25,
                'criteria_type': 'quiz_score',
                'criteria_value': 90
            },
            {
                'name': 'Course Completer',
                'description': 'Complete an entire course',
                'badge_icon': 'course-complete.png',
                'points_value': 100,
                'criteria_type': 'course_completion',
                'criteria_value': 100
            },
            {
                'name': 'Week Streak',
                'description': 'Study for 7 days in a row',
                'badge_icon': 'week-streak.png',
                'points_value': 50,
                'criteria_type': 'streak',
                'criteria_value': 7
            },
            {
                'name': 'Perfect Score',
                'description': 'Get 100% on a quiz',
                'badge_icon': 'perfect-score.png',
                'points_value': 50,
                'criteria_type': 'quiz_score',
                'criteria_value': 100
            }
        ]
        
        for achievement_info in achievements_data:
            achievement = Achievement(**achievement_info)
            db.session.add(achievement)
        
        db.session.commit()
        print(f"Created {len(achievements_data)} achievements")
        
        print("\nDatabase initialization completed successfully!")
        print("\nSample login credentials:")
        print("Admin: username='admin', password='admin123'")
        print("Teacher: username='john_smith', password='teacher123'")
        print("Student: username='alice_martin', password='student123'")

def main():
    """Main function to create and initialize the database"""
    # Create Flask app
    app = Flask(__name__)
    app.config.from_object(config['development'])
    
    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)
    
    # Create database
    if not create_database():
        print("Failed to create database. Exiting.")
        return
    
    # Initialize database with tables and data
    init_database(app)

if __name__ == '__main__':
    main()