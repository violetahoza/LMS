# app/routes/frontend.py - Complete fixed version with edit/export functionality
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, make_response
import requests

bp = Blueprint('frontend', __name__)

API_BASE_URL = 'http://localhost:5000/api'

def get_auth_headers():
    """Get authentication headers from session"""
    if 'access_token' in session:
        return {'Authorization': f'Bearer {session["access_token"]}'}
    return {}

@bp.route('/')
def index():
    """Home page - redirect based on login status"""
    if 'access_token' in session:
        user_role = session.get('user_role')
        if user_role == 'admin':
            return redirect(url_for('frontend.admin_dashboard'))
        elif user_role == 'teacher':
            return redirect(url_for('frontend.teacher_dashboard'))
        elif user_role == 'student':
            return redirect(url_for('frontend.student_dashboard'))
    return render_template('home.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form['username']  
        password = request.form['password']
        remember = 'remember' in request.form
        
        # Call API
        try:
            response = requests.post(f'{API_BASE_URL}/auth/login', json={
                'username': username, 
                'password': password,
                'remember': remember
            })
            
            if response.status_code == 200:
                data = response.json()['data']
                # Store tokens in session
                session['access_token'] = data['access_token']
                session['refresh_token'] = data['refresh_token']
                session['user_id'] = data['user']['id']
                session['user_role'] = data['user']['role']
                session['user_name'] = data['user']['full_name']
                
                flash('Login successful!', 'success')
                
                # Redirect based on role
                if data['user']['role'] == 'admin':
                    return redirect(url_for('frontend.admin_dashboard'))
                elif data['user']['role'] == 'teacher':
                    return redirect(url_for('frontend.teacher_dashboard'))
                else:
                    return redirect(url_for('frontend.student_dashboard'))
            else:
                error_data = response.json()
                error_message = error_data.get('error', 'Login failed')
                field_errors = error_data.get('field_errors', {})
                
                return render_template('auth/login.html', 
                                     error=error_message,
                                     field_errors=field_errors)
        except Exception as e:
            return render_template('auth/login.html', 
                                 error=f'Connection error: {str(e)}')
    
    return render_template('auth/login.html')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page"""
    if request.method == 'POST':
        # Client-side validation
        field_errors = {}
        
        # Basic validation
        if not request.form.get('full_name', '').strip():
            field_errors['full_name'] = 'Full name is required'
        
        if not request.form.get('username', '').strip():
            field_errors['username'] = 'Username is required'
        elif len(request.form.get('username', '').strip()) < 3:
            field_errors['username'] = 'Username must be at least 3 characters long'
        
        if not request.form.get('email', '').strip():
            field_errors['email'] = 'Email is required'
        
        if not request.form.get('password'):
            field_errors['password'] = 'Password is required'
        elif len(request.form.get('password', '')) < 8:
            field_errors['password'] = 'Password must be at least 8 characters long'
        
        if not request.form.get('confirm_password'):
            field_errors['confirm_password'] = 'Please confirm your password'
        elif request.form.get('password') != request.form.get('confirm_password'):
            field_errors['confirm_password'] = 'Passwords do not match'
        
        if not request.form.get('role'):
            field_errors['role'] = 'Please select your role'
        
        if not request.form.get('terms'):
            field_errors['terms'] = 'You must agree to the terms and conditions'
        
        # Age validation (if provided)
        if request.form.get('age'):
            try:
                age = int(request.form.get('age'))
                if age < 13 or age > 120:
                    field_errors['age'] = 'Age must be between 13 and 120'
            except ValueError:
                field_errors['age'] = 'Please enter a valid age'
        
        # If there are client-side validation errors, return to form
        if field_errors:
            return render_template('auth/register.html', field_errors=field_errors)
        
        # Prepare data for API
        data = {
            'username': request.form['username'].strip(),
            'email': request.form['email'].strip(),
            'password': request.form['password'],
            'full_name': request.form['full_name'].strip(),
            'role': request.form['role'],
            'phone': request.form.get('phone', '').strip(),
            'age': int(request.form['age']) if request.form.get('age') else None
        }
        
        try:
            response = requests.post(f'{API_BASE_URL}/auth/register', json=data)
            
            if response.status_code == 201:
                # Registration successful - now log the user in directly
                login_response = requests.post(f'{API_BASE_URL}/auth/login', json={
                    'username': data['username'],
                    'password': data['password'],
                    'remember': False
                })
                
                if login_response.status_code == 200:
                    login_data = login_response.json()['data']
                    # Store tokens in session
                    session['access_token'] = login_data['access_token']
                    session['refresh_token'] = login_data['refresh_token']
                    session['user_id'] = login_data['user']['id']
                    session['user_role'] = login_data['user']['role']
                    session['user_name'] = login_data['user']['full_name']
                    
                    flash('Registration successful! Welcome to EduPlatform!', 'success')
                    
                    # Redirect based on role
                    if login_data['user']['role'] == 'admin':
                        return redirect(url_for('frontend.admin_dashboard'))
                    elif login_data['user']['role'] == 'teacher':
                        return redirect(url_for('frontend.teacher_dashboard'))
                    else:
                        return redirect(url_for('frontend.student_dashboard'))
                else:
                    # Registration succeeded but login failed - fallback to login page
                    flash('Registration successful! Please log in.', 'success')
                    return redirect(url_for('frontend.login'))
            else:
                error_data = response.json()
                error_message = error_data.get('error', 'Registration failed')
                field_errors = error_data.get('field_errors', {})
                
                return render_template('auth/register.html', 
                                     error=error_message,
                                     field_errors=field_errors)
        except Exception as e:
            return render_template('auth/register.html', 
                                 error=f'Connection error: {str(e)}')
    
    return render_template('auth/register.html')

@bp.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('frontend.index'))

@bp.route('/admin/dashboard')
def admin_dashboard():
    """Admin dashboard"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('frontend.login'))
    
    try:
        headers = get_auth_headers()
        print(f"Making request to {API_BASE_URL}/admin/dashboard with headers: {headers}")
        
        response = requests.get(f'{API_BASE_URL}/admin/dashboard', headers=headers)
        print(f"Response status: {response.status_code}")
        print(f"Response content: {response.text[:500]}")
        
        if response.status_code == 200:
            response_data = response.json()
            dashboard_data = response_data.get('data', {})
            print(f"Dashboard data keys: {dashboard_data.keys() if dashboard_data else 'None'}")
            return render_template('admin/dashboard.html', data=dashboard_data)
        else:
            # Handle error response
            try:
                error_data = response.json()
                error_msg = error_data.get('error', 'Failed to load dashboard data')
            except:
                error_msg = f'HTTP {response.status_code}: Failed to load dashboard data'
            
            flash(f'Dashboard error: {error_msg}', 'error')
            print(f"Dashboard error: {error_msg}")
            
            # Return template with empty data
            return render_template('admin/dashboard.html', data={
                'users': {'total': 0, 'students': 0, 'teachers': 0, 'active': 0, 'recent': 0},
                'courses': {'total': 0, 'published': 0, 'recent': 0},
                'enrollments': {'total': 0, 'active': 0, 'completed': 0, 'recent': 0},
                'quizzes': {'total': 0, 'attempts': 0}
            })
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        print(f"Dashboard exception: {str(e)}")
        return render_template('admin/dashboard.html', data={
            'users': {'total': 0, 'students': 0, 'teachers': 0, 'active': 0, 'recent': 0},
            'courses': {'total': 0, 'published': 0, 'recent': 0},
            'enrollments': {'total': 0, 'active': 0, 'completed': 0, 'recent': 0},
            'quizzes': {'total': 0, 'attempts': 0}
        })

@bp.route('/admin/users')
def admin_users():
    """Admin users management - FIXED FILTERS"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('frontend.login'))
    
    page = request.args.get('page', 1, type=int)
    role = request.args.get('role', '')
    status = request.args.get('status', '')  # Fixed: status filter
    search = request.args.get('search', '')
    
    try:
        headers = get_auth_headers()
        params = {'page': page, 'per_page': 20}
        if role:
            params['role'] = role
        if status:
            params['status'] = status
        if search:
            params['search'] = search
            
        print(f"Frontend admin_users - params: {params}")
        response = requests.get(f'{API_BASE_URL}/admin/users', headers=headers, params=params)
        
        if response.status_code == 200:
            users_data = response.json()
            return render_template('admin/users.html', 
                                 users=users_data.get('users', []),
                                 total=users_data.get('total', 0),
                                 page=page,
                                 pages=users_data.get('pages', 1),
                                 current_role=role,
                                 current_status=status,  # Fixed: pass status
                                 current_search=search)
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get('error', 'Failed to load users data')
            except:
                error_msg = f'HTTP {response.status_code}: Failed to load users data'
            
            flash(f'Users error: {error_msg}', 'error')
            return render_template('admin/users.html', 
                                 users=[], total=0, page=1, pages=1,
                                 current_role=role, current_status=status, current_search=search)
    except Exception as e:
        flash(f'Error loading users: {str(e)}', 'error')
        return render_template('admin/users.html', 
                             users=[], total=0, page=1, pages=1,
                             current_role=role, current_status=status, current_search=search)

@bp.route('/admin/courses')
def admin_courses():
    """Admin courses management - FIXED FILTERS"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('frontend.login'))
    
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '')
    status = request.args.get('status', '')  # Fixed: status filter
    search = request.args.get('search', '')
    
    try:
        headers = get_auth_headers()
        params = {'page': page, 'per_page': 20}
        if category:
            params['category'] = category
        if status:
            params['status'] = status
        if search:
            params['search'] = search
            
        print(f"Frontend admin_courses - params: {params}")
        response = requests.get(f'{API_BASE_URL}/admin/courses', headers=headers, params=params)
        
        if response.status_code == 200:
            courses_data = response.json()
            return render_template('admin/courses.html', 
                                 courses=courses_data.get('courses', []),
                                 total=courses_data.get('total', 0),
                                 page=page,
                                 pages=courses_data.get('pages', 1),
                                 current_category=category,
                                 current_status=status,  # Fixed: pass status
                                 current_search=search)
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get('error', 'Failed to load courses data')
            except:
                error_msg = f'HTTP {response.status_code}: Failed to load courses data'
            
            flash(f'Courses error: {error_msg}', 'error')
            return render_template('admin/courses.html', 
                                 courses=[], total=0, page=1, pages=1,
                                 current_category=category, current_status=status, current_search=search)
    except Exception as e:
        flash(f'Error loading courses: {str(e)}', 'error')
        return render_template('admin/courses.html', 
                             courses=[], total=0, page=1, pages=1,
                             current_category=category, current_status=status, current_search=search)

# Add these new routes to your frontend.py:

@bp.route('/admin/courses/<int:course_id>/delete', methods=['POST'])
def delete_course(course_id):
    """Delete a course"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        headers = get_auth_headers()
        response = requests.delete(f'{API_BASE_URL}/admin/courses/{course_id}', headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            try:
                error_data = response.json()
                return jsonify({'error': error_data.get('error', 'Failed to delete course')}), response.status_code
            except:
                return jsonify({'error': f'HTTP {response.status_code}: Failed to delete course'}), response.status_code
    except Exception as e:
        return jsonify({'error': f'Connection error: {str(e)}'}), 500

@bp.route('/admin/courses/export')
def export_courses():
    """Export courses to CSV"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('frontend.login'))
    
    try:
        headers = get_auth_headers()
        
        # Get current filter parameters
        category = request.args.get('category', '')
        status = request.args.get('status', '')
        search = request.args.get('search', '')
        
        params = {}
        if category:
            params['category'] = category
        if status:
            params['status'] = status
        if search:
            params['search'] = search
        
        response = requests.get(f'{API_BASE_URL}/admin/courses/export', 
                              headers=headers, 
                              params=params)
        
        if response.status_code == 200:
            # Create Flask response with CSV content
            output = make_response(response.content)
            output.headers["Content-Disposition"] = response.headers.get('Content-Disposition')
            output.headers["Content-type"] = response.headers.get('Content-Type')
            return output
        else:
            flash('Failed to export courses', 'error')
            return redirect(url_for('frontend.admin_courses'))
            
    except Exception as e:
        flash(f'Error exporting courses: {str(e)}', 'error')
        return redirect(url_for('frontend.admin_courses'))
@bp.route('/admin/reports')
def admin_reports():
    """Admin reports page"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('frontend.login'))
    
    days = request.args.get('days', 30, type=int)
    
    try:
        headers = get_auth_headers()
        
        # Get user activity report
        activity_response = requests.get(
            f'{API_BASE_URL}/admin/reports/user-activity',
            headers=headers,
            params={'days': days}
        )
        
        # Get course performance report
        performance_response = requests.get(
            f'{API_BASE_URL}/admin/reports/course-performance',
            headers=headers
        )
        
        activity_data = {}
        performance_data = {}
        
        if activity_response.status_code == 200:
            activity_data = activity_response.json()
        else:
            activity_data = {
                'period_days': days,
                'user_registrations': [],
                'course_enrollments': [],
                'quiz_attempts': []
            }
            flash('Failed to load activity data', 'warning')
        
        if performance_response.status_code == 200:
            performance_data = performance_response.json()
        else:
            performance_data = {
                'courses': [],
                'total_courses': 0
            }
            flash('Failed to load performance data', 'warning')
        
        return render_template('admin/reports.html', 
                             activity_data=activity_data,
                             performance_data=performance_data,
                             selected_days=days)
    except Exception as e:
        flash(f'Error loading reports: {str(e)}', 'error')
        return render_template('admin/reports.html', 
                             activity_data={
                                 'period_days': days,
                                 'user_registrations': [],
                                 'course_enrollments': [],
                                 'quiz_attempts': []
                             }, 
                             performance_data={
                                 'courses': [],
                                 'total_courses': 0
                             },
                             selected_days=days)

# AJAX endpoints for admin actions
@bp.route('/admin/users/<int:user_id>/toggle-active', methods=['POST'])
def toggle_user_active(user_id):
    """Toggle user active status"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        headers = get_auth_headers()
        response = requests.post(f'{API_BASE_URL}/admin/users/{user_id}/toggle-active', headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            try:
                error_data = response.json()
                return jsonify({'error': error_data.get('error', 'Failed to toggle user status')}), response.status_code
            except:
                return jsonify({'error': f'HTTP {response.status_code}: Failed to toggle user status'}), response.status_code
    except Exception as e:
        return jsonify({'error': f'Connection error: {str(e)}'}), 500

@bp.route('/admin/users/<int:user_id>/details', methods=['GET'])
def get_user_details(user_id):
    """Get user details for modal"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        headers = get_auth_headers()
        response = requests.get(f'{API_BASE_URL}/admin/users/{user_id}', headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            try:
                error_data = response.json()
                return jsonify({'error': error_data.get('error', 'Failed to load user details')}), response.status_code
            except:
                return jsonify({'error': f'HTTP {response.status_code}: Failed to load user details'}), response.status_code
    except Exception as e:
        return jsonify({'error': f'Connection error: {str(e)}'}), 500

@bp.route('/admin/users/<int:user_id>/edit', methods=['POST'])
def edit_user(user_id):
    """Update user information"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        headers = get_auth_headers()
        data = request.get_json()
        
        response = requests.put(f'{API_BASE_URL}/admin/users/{user_id}', 
                              headers=headers, 
                              json=data)
        
        if response.status_code == 200:
            return response.json()
        else:
            try:
                error_data = response.json()
                return jsonify({'error': error_data.get('error', 'Failed to update user')}), response.status_code
            except:
                return jsonify({'error': f'HTTP {response.status_code}: Failed to update user'}), response.status_code
    except Exception as e:
        return jsonify({'error': f'Connection error: {str(e)}'}), 500

@bp.route('/admin/users/export')
def export_users():
    """Export users to CSV"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('frontend.login'))
    
    try:
        headers = get_auth_headers()
        
        # Get current filter parameters
        role = request.args.get('role', '')
        status = request.args.get('status', '')
        search = request.args.get('search', '')
        
        params = {}
        if role:
            params['role'] = role
        if status:
            params['status'] = status
        if search:
            params['search'] = search
        
        response = requests.get(f'{API_BASE_URL}/admin/users/export', 
                              headers=headers, 
                              params=params)
        
        if response.status_code == 200:
            # Create Flask response with CSV content
            output = make_response(response.content)
            output.headers["Content-Disposition"] = response.headers.get('Content-Disposition')
            output.headers["Content-type"] = response.headers.get('Content-Type')
            return output
        else:
            flash('Failed to export users', 'error')
            return redirect(url_for('frontend.admin_users'))
            
    except Exception as e:
        flash(f'Error exporting users: {str(e)}', 'error')
        return redirect(url_for('frontend.admin_users'))

@bp.route('/admin/courses/<int:course_id>/toggle-published', methods=['POST'])
def toggle_course_published(course_id):
    """Toggle course published status"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        headers = get_auth_headers()
        response = requests.post(f'{API_BASE_URL}/admin/courses/{course_id}/toggle-published', headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            try:
                error_data = response.json()
                return jsonify({'error': error_data.get('error', 'Failed to toggle course status')}), response.status_code
            except:
                return jsonify({'error': f'HTTP {response.status_code}: Failed to toggle course status'}), response.status_code
    except Exception as e:
        return jsonify({'error': f'Connection error: {str(e)}'}), 500

@bp.route('/student/dashboard')
def student_dashboard():
    """Student dashboard (placeholder)"""
    if not session.get('access_token') or session.get('user_role') != 'student':
        flash('Access denied. Student privileges required.', 'error')
        return redirect(url_for('frontend.login'))
    
    return render_template('student/dashboard.html')

@bp.route('/teacher/dashboard')
def teacher_dashboard():
    """Teacher dashboard (placeholder)"""
    if not session.get('access_token') or session.get('user_role') != 'teacher':
        flash('Access denied. Teacher privileges required.', 'error')
        return redirect(url_for('frontend.login'))
    
    return render_template('teacher/dashboard.html')

# Debug endpoints
@bp.route('/debug/session')
def debug_session():
    """Debug session data"""
    if not session.get('access_token'):
        return jsonify({'error': 'No session data'})
    
    return jsonify({
        'has_token': 'access_token' in session,
        'user_role': session.get('user_role'),
        'user_id': session.get('user_id'),
        'user_name': session.get('user_name'),
        'token_preview': session['access_token'][:20] + '...' if session.get('access_token') else None
    })

@bp.route('/debug/test-api')
def debug_test_api():
    """Test API connection"""
    if not session.get('access_token'):
        return jsonify({'error': 'No session token'})
    
    try:
        headers = get_auth_headers()
        response = requests.get(f'{API_BASE_URL}/admin/test-auth', headers=headers)
        
        return jsonify({
            'status_code': response.status_code,
            'response': response.json() if response.content else 'No content',
            'headers_sent': headers
        })
    except Exception as e:
        return jsonify({'error': str(e)})