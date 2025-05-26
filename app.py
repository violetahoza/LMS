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
    
    return app


app = create_application()

if __name__ == '__main__':
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