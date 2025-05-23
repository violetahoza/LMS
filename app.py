"""
Learning Management System (LMS) - Main Application
This is the main Flask application file that creates and runs the LMS.
"""

import os
from flask import Flask, jsonify

def create_application():
    """Create Flask application with proper configuration"""
    # Get environment
    config_name = os.environ.get('FLASK_ENV', 'development')
    
    # Create app
    from app import create_app
    app = create_app(config_name)
    
    # Register frontend routes
    from app.routes import frontend
    app.register_blueprint(frontend.bp)
    
    # Add global error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Resource not found',
            'message': 'The requested resource could not be found.'
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        # Import db here to avoid circular imports
        from app import db
        db.session.rollback()
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred. Please try again later.'
        }), 500
    
    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            'error': 'Forbidden',
            'message': 'You do not have permission to access this resource.'
        }), 403
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'error': 'Bad request',
            'message': 'The request could not be understood by the server.'
        }), 400
    
    @app.errorhandler(422)
    def unprocessable_entity(error):
        return jsonify({
            'error': 'Unprocessable entity',
            'message': 'The request was well-formed but was unable to be followed due to semantic errors.'
        }), 422
    
    # Add health check endpoint
    @app.route('/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'message': 'LMS API is running',
            'version': '1.0.0'
        }), 200
    
    # Add API info endpoint
    @app.route('/api')
    def api_info():
        return jsonify({
            'name': 'Learning Management System API',
            'version': '1.0.0',
            'description': 'Backend API for the LMS platform',
            'endpoints': {
                'authentication': '/api/auth',
                'courses': '/api/courses',
                'lessons': '/api/lessons',
                'quizzes': '/api/quizzes',
                'assignments': '/api/assignments',
                'admin': '/api/admin',
                'student': '/api/student'
            }
        }), 200
    
    return app

# Create the application
app = create_application()

if __name__ == '__main__':
    # Run the application
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    print("=" * 50)
    print("🎓 Learning Management System")
    print("=" * 50)
    print(f"Environment: {os.environ.get('FLASK_ENV', 'development')}")
    print(f"Debug Mode: {debug}")
    print(f"Port: {port}")
    print("=" * 50)
    print("Available endpoints:")
    print("  GET  /                - Home page")
    print("  GET  /login           - Login page")  
    print("  GET  /register        - Registration page")
    print("  GET  /admin/dashboard - Admin dashboard")
    print("  GET  /health          - Health check")
    print("  GET  /api             - API information")
    print("=" * 50)
    
    # Initialize database and admin user
    with app.app_context():
        try:
            from app import db
            from app.models import User, UserRole
            
            # Create tables
            db.create_all()
            print("✅ Database tables created/verified")
            
            # Check for admin user
            admin = User.query.filter_by(username='admin').first()
            if not admin:
                print("🔧 Creating admin user...")
                admin = User(
                    username='admin',
                    email='admin@lms.com',
                    full_name='System Administrator',
                    role=UserRole.ADMIN,
                    phone='555-0001',
                    age=35,
                    is_active=True
                )
                admin.set_password('Admin123!')
                db.session.add(admin)
                db.session.commit()
                print("✅ Admin user created (admin/Admin123!)")
            else:
                print("✅ Admin user exists")
                
        except Exception as e:
            print(f"⚠️ Database initialization warning: {e}")
    
    print("🚀 Starting server...")
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )