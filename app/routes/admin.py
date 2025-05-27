from flask import Blueprint, request, jsonify, make_response
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
        user_id_str = get_jwt_identity()
        
        if not user_id_str:
            return jsonify({'error': 'Authentication required'}), 401
        
        try:
            user_id = int(user_id_str)
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid user ID'}), 400
        
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if not user.is_admin():
            return jsonify({'error': 'Access denied. Admin role required'}), 403
        
        dashboard_data = AdminService.get_dashboard()
        
        return jsonify({
            'message': 'Dashboard data retrieved successfully',
            'data': dashboard_data
        }), 200
        
    except Exception as e:
        print(f"Dashboard error: {str(e)}")
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
    status = request.args.get('status')
    search = request.args.get('search')
    
    try:
        data = AdminService.get_users(
            page=page,
            per_page=per_page,
            role=role,
            status=status,
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
    """Get all courses with detailed information"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    category = request.args.get('category')
    status = request.args.get('status')
    search = request.args.get('search')
    
    try:
        data = AdminService.get_all_courses(
            page=page,
            per_page=per_page,
            category=category,
            status=status,
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

@bp.route('/reports/user-activity-overview', methods=['GET'])
@admin_required()
def get_user_activity_overview():
    """Get user overview chart data for dashboard"""
    days = request.args.get('days', 30, type=int)
    try:
        data = AdminService.get_user_overview_chart(days)
        return jsonify(data), 200
    except Exception as e:
        print(f"User activity report error: {str(e)}")
        return jsonify({
            "labels": [],
            "new_users": [],
            "active_users": []
        }), 200

@bp.route('/reports/course-categories', methods=['GET'])
@admin_required()
def get_course_categories():
    """Return course category distribution"""
    try:
        data = AdminService.get_course_categories_distribution()
        return jsonify(data), 200
    except Exception as e:
        print(f"Course category distribution error: {str(e)}")
        return jsonify({}), 500
    
