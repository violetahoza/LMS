import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from config import config

db = SQLAlchemy()
jwt = JWTManager()

def create_app(config_name=None):
    """Application factory"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    db.init_app(app)
    jwt.init_app(app)
    CORS(app, origins=app.config.get('CORS_ORIGINS', ['http://localhost:3000']))
    
    setup_logging(app)
    
    register_blueprints(app)
    
    create_directories(app)
    
    with app.app_context():
        try:
            db.create_all()
            print("✅ Database tables created/verified")
        except Exception as e:
            print(f"⚠️ Database table creation warning: {e}")
    
    return app

def register_blueprints(app):
    """Register all blueprints"""
    try:
        from app.routes import auth, courses, lessons, quizzes, assignments, admin, student, teacher, messages, notifications, quiz_grading, quiz_history, certificates
        
        app.register_blueprint(auth.bp)
        app.register_blueprint(courses.bp)
        app.register_blueprint(lessons.bp)
        app.register_blueprint(quizzes.bp)
        app.register_blueprint(assignments.bp)
        app.register_blueprint(admin.bp)
        app.register_blueprint(student.bp)
        app.register_blueprint(teacher.bp)
        app.register_blueprint(messages.bp)
        app.register_blueprint(notifications.bp)
        app.register_blueprint(quiz_grading.bp)
        app.register_blueprint(quiz_history.bp)
        app.register_blueprint(certificates.bp)

        print("✅ All blueprints registered successfully")
    except Exception as e:
        print(f"❌ Error registering blueprints: {e}")
        import traceback
        traceback.print_exc()

def setup_logging(app):
    """Setup application logging"""
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = logging.FileHandler('logs/app.log')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('EduPlatform startup')

def create_directories(app):
    """Create necessary directories"""
    upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    
    subdirs = ['assignments', 'avatars', 'course_materials']
    for subdir in subdirs:
        path = os.path.join(upload_folder, subdir)
        if not os.path.exists(path):
            os.makedirs(path)

