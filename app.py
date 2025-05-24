"""
Learning Management System (LMS) - Main Application
This is the main Flask application file that creates and runs the LMS.
"""

import os
from flask import Flask, jsonify

def create_application():
    """Create Flask application with proper configuration"""
    config_name = os.environ.get('FLASK_ENV', 'development')
    
    from app import create_app
    app = create_app(config_name)
    
    from app.routes import frontend
    app.register_blueprint(frontend.bp)
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Resource not found',
            'message': 'The requested resource could not be found.'
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        print("=" * 80)
        print("500 INTERNAL SERVER ERROR OCCURRED")
        print("=" * 80)
        
        # Print the full traceback
        import traceback
        traceback.print_exc()
        
        # Try to get more details from the database
        from app import db
        try:
            db.session.rollback()
            print("Database session rolled back successfully")
        except Exception as db_error:
            print(f"Database rollback failed: {db_error}")
        
        print("=" * 80)
        
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred. Check server logs for details.'
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
    
    @app.route('/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'message': 'LMS API is running',
            'version': '1.0.0'
        }), 200
    
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
    
    @app.route('/test/db')
    def test_db():
        try:
            from app import db
            from app.models import User
            
            # Test basic query
            user_count = User.query.count()
            
            return jsonify({
                'status': 'success',
                'message': 'Database connection working',
                'user_count': user_count
            })
        except Exception as e:
            import traceback
            return jsonify({
                'status': 'error',
                'message': str(e),
                'traceback': traceback.format_exc()
            }), 500
    
    # Test imports
    @app.route('/test/imports')
    def test_imports():
        try:
            # Test all critical imports
            from werkzeug.security import generate_password_hash, check_password_hash
            from flask_jwt_extended import create_access_token, create_refresh_token
            from app.models import User, UserRole, db
            from app.services.auth_service import AuthService
            
            return jsonify({
                'status': 'success',
                'message': 'All imports working'
            })
        except Exception as e:
            import traceback
            return jsonify({
                'status': 'error',
                'message': str(e),
                'traceback': traceback.format_exc()
            }), 500
    
    # Test simple registration
    @app.route('/test/register')
    def test_register():
        try:
            from app.models import User, UserRole, db
            
            # Try to create a simple user
            test_user = User(
                username='test123',
                email='test123@example.com',
                full_name='Test User',
                role=UserRole.STUDENT,
                is_active=True
            )
            
            test_user.set_password('TestPass123!')
            
            # Don't actually save, just test creation
            user_dict = test_user.to_dict()
            
            return jsonify({
                'status': 'success',
                'message': 'User creation test passed',
                'user': user_dict
            })
        except Exception as e:
            import traceback
            return jsonify({
                'status': 'error',
                'message': str(e),
                'traceback': traceback.format_exc()
            }), 500
    
    return app


app = create_application()

def run_diagnostics():
    """Run comprehensive diagnostics"""
    print("=" * 60)
    print("RUNNING LMS DIAGNOSTICS")
    print("=" * 60)
    
    # Test 1: Basic imports
    print("1. Testing imports...")
    try:
        import flask
        import flask_sqlalchemy
        import flask_jwt_extended
        import werkzeug.security
        print("   ✅ Core Flask packages imported successfully")
    except Exception as e:
        print(f"   ❌ Import error: {e}")
        return
    
    # Test 2: App creation
    print("2. Testing app creation...")
    try:
        from app import create_app
        app = create_app('development')
        print("   ✅ App created successfully")
    except Exception as e:
        print(f"   ❌ App creation error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 3: Database connection
    print("3. Testing database connection...")
    try:
        with app.app_context():
            from app import db
            from app.models import User
            
            # Test connection
            db.engine.execute('SELECT 1')
            print("   ✅ Database connection successful")
            
            # Test table existence
            user_count = User.query.count()
            print(f"   ✅ Users table accessible, {user_count} users found")
            
    except Exception as e:
        print(f"   ❌ Database error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 4: Model operations
    print("4. Testing model operations...")
    try:
        with app.app_context():
            from app.models import User, UserRole
            
            # Test user creation (without saving)
            test_user = User(
                username='diagnostic_test',
                email='test@example.com',
                full_name='Test User',
                role=UserRole.STUDENT,
                is_active=True
            )
            
            test_user.set_password('TestPass123!')
            user_dict = test_user.to_dict()
            print("   ✅ User model operations successful")
            
    except Exception as e:
        print(f"   ❌ Model operations error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 5: JWT operations
    print("5. Testing JWT operations...")
    try:
        with app.app_context():
            from flask_jwt_extended import create_access_token
            
            token = create_access_token(identity="test_user")
            print("   ✅ JWT token creation successful")
            
    except Exception as e:
        print(f"   ❌ JWT error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("=" * 60)
    print("✅ ALL DIAGNOSTICS PASSED!")
    print("=" * 60)

if __name__ == '__main__':
    run_diagnostics()
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
    
    with app.app_context():
        try:
            from app import db
            from app.models import User, UserRole
            
            db.create_all()
            print("✅ Database tables created/verified")
            
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