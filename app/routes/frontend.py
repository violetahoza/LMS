# Save as: app/routes/frontend.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
import requests

bp = Blueprint('frontend', __name__)

API_BASE_URL = 'http://localhost:5000/api'

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
        headers = {'Authorization': f'Bearer {session["access_token"]}'}
        response = requests.get(f'{API_BASE_URL}/admin/dashboard', headers=headers)
        
        if response.status_code == 200:
            dashboard_data = response.json()
            return render_template('admin/dashboard.html', data=dashboard_data)
        else:
            flash('Failed to load dashboard data', 'error')
            return render_template('admin/dashboard.html', data={})
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('admin/dashboard.html', data={})

@bp.route('/admin/users')
def admin_users():
    """Admin users management"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('frontend.login'))
    
    page = request.args.get('page', 1, type=int)
    role = request.args.get('role', '')
    search = request.args.get('search', '')
    
    try:
        headers = {'Authorization': f'Bearer {session["access_token"]}'}
        params = {'page': page, 'per_page': 20}
        if role:
            params['role'] = role
        if search:
            params['search'] = search
            
        response = requests.get(f'{API_BASE_URL}/admin/users', headers=headers, params=params)
        
        if response.status_code == 200:
            users_data = response.json()
            return render_template('admin/users.html', 
                                 users=users_data['users'],
                                 total=users_data['total'],
                                 page=page,
                                 pages=users_data['pages'],
                                 current_role=role,
                                 current_search=search)
        else:
            flash('Failed to load users data', 'error')
            return render_template('admin/users.html', users=[], total=0, page=1, pages=1)
    except Exception as e:
        flash(f'Error loading users: {str(e)}', 'error')
        return render_template('admin/users.html', users=[], total=0, page=1, pages=1)

@bp.route('/admin/courses')
def admin_courses():
    """Admin courses management"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('frontend.login'))
    
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '')
    
    try:
        headers = {'Authorization': f'Bearer {session["access_token"]}'}
        params = {'page': page, 'per_page': 20}
        if category:
            params['category'] = category
            
        response = requests.get(f'{API_BASE_URL}/admin/courses', headers=headers, params=params)
        
        if response.status_code == 200:
            courses_data = response.json()
            return render_template('admin/courses.html', 
                                 courses=courses_data['courses'],
                                 total=courses_data['total'],
                                 page=page,
                                 pages=courses_data['pages'],
                                 current_category=category)
        else:
            flash('Failed to load courses data', 'error')
            return render_template('admin/courses.html', courses=[], total=0, page=1, pages=1)
    except Exception as e:
        flash(f'Error loading courses: {str(e)}', 'error')
        return render_template('admin/courses.html', courses=[], total=0, page=1, pages=1)

@bp.route('/admin/reports')
def admin_reports():
    """Admin reports page"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('frontend.login'))
    
    days = request.args.get('days', 30, type=int)
    
    try:
        headers = {'Authorization': f'Bearer {session["access_token"]}'}
        
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
        
        activity_data = activity_response.json() if activity_response.status_code == 200 else {}
        performance_data = performance_response.json() if performance_response.status_code == 200 else {}
        
        return render_template('admin/reports.html', 
                             activity_data=activity_data,
                             performance_data=performance_data,
                             selected_days=days)
    except Exception as e:
        flash(f'Error loading reports: {str(e)}', 'error')
        return render_template('admin/reports.html', 
                             activity_data={}, 
                             performance_data={},
                             selected_days=days)

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

# AJAX endpoints for admin actions
@bp.route('/admin/users/<int:user_id>/toggle-active', methods=['POST'])
def toggle_user_active(user_id):
    """Toggle user active status"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        return {'error': 'Access denied'}, 403
    
    try:
        headers = {'Authorization': f'Bearer {session["access_token"]}'}
        response = requests.post(f'{API_BASE_URL}/admin/users/{user_id}/toggle-active', headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            return response.json(), response.status_code
    except Exception as e:
        return {'error': str(e)}, 500

@bp.route('/admin/courses/<int:course_id>/toggle-published', methods=['POST'])
def toggle_course_published(course_id):
    """Toggle course published status"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        return {'error': 'Access denied'}, 403
    
    try:
        headers = {'Authorization': f'Bearer {session["access_token"]}'}
        response = requests.post(f'{API_BASE_URL}/admin/courses/{course_id}/toggle-published', headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            return response.json(), response.status_code
    except Exception as e:
        return {'error': str(e)}, 500