# Create check_routes.py to see what routes are registered
#!/usr/bin/env python3

import sys
import os

# Add the project directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def check_routes():
    try:
        print("🔍 Checking registered routes...")
        
        from app import create_app
        app = create_app('development')
        
        print("✅ App created successfully")
        
        with app.app_context():
            # List all registered routes
            print("\n📋 All registered routes:")
            for rule in app.url_map.iter_rules():
                methods = ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))
                print(f"  {methods:20} {rule.rule}")
            
            # Check specifically for admin routes
            admin_routes = [rule for rule in app.url_map.iter_rules() if '/admin' in rule.rule]
            print(f"\n🔧 Admin routes found: {len(admin_routes)}")
            for route in admin_routes:
                methods = ','.join(sorted(route.methods - {'HEAD', 'OPTIONS'}))
                print(f"  {methods:20} {route.rule}")
            
            # Check if admin blueprint is registered
            blueprints = list(app.blueprints.keys())
            print(f"\n📦 Registered blueprints: {blueprints}")
            
            if 'admin' in blueprints:
                print("✅ Admin blueprint is registered")
            else:
                print("❌ Admin blueprint is NOT registered")
                
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    check_routes()