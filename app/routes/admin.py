from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.admin_service import AdminService
from app.utils.base_controller import BaseController
from app.utils.decorators import admin_required
from app.models import User 

bp = Blueprint('admin', __name__, url_prefix='/api/admin')

@bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard():
    """Get admin dashboard statistics"""
    try:
        # Check user authentication and role first
        user_id_str = get_jwt_identity()
        print(f"Dashboard - User ID from JWT: {user_id_str} (type: {type(user_id_str)})")
        
        if not user_id_str:
            print("Dashboard - No user ID from JWT")
            return jsonify({'error': 'Authentication required'}), 401
        
        # Convert string user ID to int for database query
        try:
            user_id = int(user_id_str)
        except (ValueError, TypeError):
            print(f"Dashboard - Invalid user ID format: {user_id_str}")
            return jsonify({'error': 'Invalid user ID'}), 400
        
        user = User.query.get(user_id)
        print(f"Dashboard - User object: {user}")
        
        if not user:
            print("Dashboard - User not found")
            return jsonify({'error': 'User not found'}), 404
        
        print(f"Dashboard - User role: {user.role}")
        print(f"Dashboard - Is admin: {user.is_admin()}")
        
        if not user.is_admin():
            print("Dashboard - Access denied, not admin")
            return jsonify({'error': 'Access denied. Admin role required'}), 403
        
        print("Dashboard - Admin access confirmed, getting data...")
        
        # Get dashboard data using the service
        dashboard_data = AdminService.get_dashboard()
        
        print("Dashboard - Returning data successfully")
        return jsonify({
            'message': 'Dashboard data retrieved successfully',
            'data': dashboard_data
        }), 200
        
    except Exception as e:
        print(f"Dashboard - Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return error with empty data structure
        return jsonify({
            'error': f'Dashboard error: {str(e)}',
            'data': {
                'users': {'total': 0, 'students': 0, 'teachers': 0, 'active': 0, 'recent': 0},
                'courses': {'total': 0, 'published': 0, 'recent': 0},
                'enrollments': {'total': 0, 'active': 0, 'completed': 0, 'recent': 0},
                'quizzes': {'total': 0, 'attempts': 0}
            }
        }), 500

@bp.route('/users', methods=['GET'])
@admin_required()
def get_users():
    """Get all users with filtering and pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    role = request.args.get('role')
    status = request.args.get('status')  # Changed from active_only to status
    search = request.args.get('search')
    
    print(f"Admin get_users - Filters: role={role}, status={status}, search={search}")
    
    try:
        data = AdminService.get_users(
            page=page,
            per_page=per_page,
            role=role,
            status=status,  # Pass status instead of active_only
            search=search
        )
        return jsonify(data), 200
    except Exception as e:
        print(f"Get users error: {str(e)}")
        return jsonify({
            'users': [],
            'total': 0,
            'page': 1,
            'per_page': per_page,
            'pages': 1
        }), 200

@bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required()
def get_user(user_id):
    """Get detailed user information"""
    return BaseController.handle_request(
        AdminService.get_user,
        user_id
    )

@bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required()
def update_user(user_id):
    """Update user information"""
    admin_id_str = get_jwt_identity()
    try:
        admin_id = int(admin_id_str)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid admin ID'}), 400
        
    return BaseController.handle_request(
        AdminService.update_user,
        admin_id,
        user_id,
        request.get_json(),
        success_message="User updated successfully"
    )

@bp.route('/users/export', methods=['GET'])
@admin_required()
def export_users():
    """Export users to CSV"""
    role = request.args.get('role')
    status = request.args.get('status')
    search = request.args.get('search')
    
    try:
        from flask import make_response
        
        result = AdminService.export_users(role=role, status=status, search=search)
        
        response = make_response(result['csv_content'])
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename={result["filename"]}'
        
        return response
    except Exception as e:
        print(f"Export users error: {str(e)}")
        return jsonify({'error': f'Export failed: {str(e)}'}), 500

@bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@admin_required()
def toggle_user_active(user_id):
    """Toggle user active status"""
    admin_id_str = get_jwt_identity()
    # Convert string to int
    try:
        admin_id = int(admin_id_str)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid admin ID'}), 400
        
    return BaseController.handle_request(
        AdminService.toggle_user_active,
        admin_id,
        user_id,
        success_message="User status toggled successfully"
    )

@bp.route('/courses', methods=['GET'])
@admin_required()
def get_all_courses():
    """Get all courses with detailed information - FIXED FILTERS"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    category = request.args.get('category')
    status = request.args.get('status')  # Changed from published_only to status
    search = request.args.get('search')
    
    print(f"Admin get_courses - Filters: category={category}, status={status}, search={search}")
    
    try:
        data = AdminService.get_all_courses(
            page=page,
            per_page=per_page,
            category=category,
            status=status,  # Pass status instead of published_only
            search=search
        )
        return jsonify(data), 200
    except Exception as e:
        print(f"Get courses error: {str(e)}")
        return jsonify({
            'courses': [],
            'total': 0,
            'page': 1,
            'per_page': per_page,
            'pages': 1
        }), 200

@bp.route('/courses/<int:course_id>', methods=['DELETE'])
@admin_required()
def delete_course(course_id):
    """Delete a course"""
    admin_id_str = get_jwt_identity()
    try:
        admin_id = int(admin_id_str)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid admin ID'}), 400
        
    return BaseController.handle_request(
        AdminService.delete_course,
        admin_id,
        course_id,
        success_message="Course deleted successfully"
    )

@bp.route('/courses/export', methods=['GET'])
@admin_required()
def export_courses():
    """Export courses to CSV"""
    category = request.args.get('category')
    status = request.args.get('status')
    search = request.args.get('search')
    
    try:
        from flask import make_response
        
        result = AdminService.export_courses(category=category, status=status, search=search)
        
        response = make_response(result['csv_content'])
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename={result["filename"]}'
        
        return response
    except Exception as e:
        print(f"Export courses error: {str(e)}")
        return jsonify({'error': f'Export failed: {str(e)}'}), 500

@bp.route('/courses/<int:course_id>/toggle-published', methods=['POST'])
@admin_required()
def toggle_course_published(course_id):
    """Toggle course published status"""
    return BaseController.handle_request(
        AdminService.toggle_course_published,
        course_id,
        success_message="Course status toggled successfully"
    )

@bp.route('/reports/user-activity', methods=['GET'])
@admin_required()
def get_user_activity_report():
    """Get user activity report"""
    days = request.args.get('days', 30, type=int)
    try:
        data = AdminService.get_user_activity_report(days)
        return jsonify(data), 200
    except Exception as e:
        print(f"User activity report error: {str(e)}")
        return jsonify({
            'period_days': days,
            'user_registrations': [],
            'course_enrollments': [],
            'quiz_attempts': []
        }), 200

@bp.route('/reports/course-performance', methods=['GET'])
@admin_required()
def get_course_performance_report():
    """Get course performance report"""
    try:
        data = AdminService.get_course_performance_report()
        return jsonify(data), 200
    except Exception as e:
        print(f"Course performance report error: {str(e)}")
        return jsonify({
            'courses': [],
            'total_courses': 0
        }), 200

@bp.route('/achievements', methods=['GET'])
@admin_required()
def get_achievements():
    """Get all achievements"""
    try:
        data = AdminService.get_achievements()
        return jsonify(data), 200
    except Exception as e:
        print(f"Get achievements error: {str(e)}")
        return jsonify({
            'achievements': [],
            'total': 0
        }), 200

@bp.route('/achievements', methods=['POST'])
@admin_required()
def create_achievement():
    """Create a new achievement"""
    return BaseController.handle_request(
        AdminService.create_achievement,
        request.get_json(),
        success_message="Achievement created successfully",
        success_code=201
    )

# Debug endpoints
@bp.route('/test', methods=['GET'])
def test_admin():
    """Simple test endpoint to check admin access"""
    try:
        return jsonify({
            'message': 'Admin test endpoint working',
            'data': {'test': 'success'}
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Test failed: {str(e)}'
        }), 500

@bp.route('/test-auth', methods=['GET'])
@jwt_required()
def test_auth():
    """Test JWT authentication"""
    try:
        user_id_str = get_jwt_identity()
        print(f"Test auth - User ID: {user_id_str} (type: {type(user_id_str)})")
        
        # Convert to int
        try:
            user_id = int(user_id_str)
        except (ValueError, TypeError):
            return jsonify({
                'error': 'Invalid user ID format',
                'user_id_received': user_id_str,
                'type': str(type(user_id_str))
            }), 400
        
        user = User.query.get(user_id)
        
        return jsonify({
            'message': 'Auth test successful',
            'user_id_str': user_id_str,
            'user_id_int': user_id,
            'user_exists': user is not None,
            'user_role': user.role.value if user else None,
            'is_admin': user.is_admin() if user else False
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Auth test failed: {str(e)}'
        }), 500