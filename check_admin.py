# Fixed check_admin.py
#!/usr/bin/env python3

import sys
import os

# Add the project directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def check_admin_user():
    try:
        # Import after setting path
        from app import create_app
        from app.models import db, User, UserRole
        
        print("🔍 Creating Flask app and checking admin user...")
        
        # Create app with development config
        app = create_app('development')
        
        # Push application context
        with app.app_context():
            print("✅ Flask app context established")
            
            # Check database connection
            try:
                # Simple query to test connection
                user_count = db.session.execute(db.text("SELECT COUNT(*) FROM users")).scalar()
                print(f"✅ Database connected - found {user_count} users")
            except Exception as e:
                print(f"❌ Database connection failed: {e}")
                return False
            
            # Check all users
            all_users = User.query.all()
            print(f"Total users in database: {len(all_users)}")
            
            for user in all_users:
                print(f"- {user.username} ({user.email}) - Role: {user.role} - Active: {user.is_active}")
            
            # Check specifically for admin
            admin_users = User.query.filter_by(role=UserRole.ADMIN).all()
            print(f"\nAdmin users found: {len(admin_users)}")
            
            if not admin_users:
                print("❌ No admin user found! Creating one...")
                
                # Create admin user
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
                
                print("✅ Admin user created successfully!")
                print("Username: admin")
                print("Password: Admin123!")
                
            else:
                admin = admin_users[0]
                print(f"✅ Admin user exists:")
                print(f"Username: {admin.username}")
                print(f"Email: {admin.email}")
                print(f"Active: {admin.is_active}")
                print(f"Role: {admin.role}")
                
                # Ensure user is active
                if not admin.is_active:
                    print("⚠️  Admin user is inactive, activating...")
                    admin.is_active = True
                    db.session.commit()
                    print("✅ Admin user activated")
                
                # Test password
                if admin.check_password('Admin123!'):
                    print("✅ Password is correct")
                else:
                    print("❌ Password is wrong, updating...")
                    admin.set_password('Admin123!')
                    db.session.commit()
                    print("✅ Password updated to: Admin123!")
            
            # Final test
            print("\n🔐 Testing admin login...")
            admin = User.query.filter_by(username='admin').first()
            if admin and admin.check_password('Admin123!') and admin.is_active and admin.role == UserRole.ADMIN:
                print("✅ Admin can login successfully")
                print(f"Admin ID: {admin.id}")
                print(f"Admin role: {admin.role}")
                print(f"Is admin check: {admin.is_admin()}")
                return True
            else:
                print("❌ Admin login failed")
                if admin:
                    print(f"- User exists: True")
                    print(f"- Password correct: {admin.check_password('Admin123!')}")
                    print(f"- Is active: {admin.is_active}")
                    print(f"- Role: {admin.role}")
                    print(f"- Is admin: {admin.is_admin()}")
                return False
                
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = check_admin_user()
    if success:
        print("\n🎉 Admin user is ready!")
    else:
        print("\n💥 Admin user setup failed!")