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
        
        try:
            response = requests.post(f'{API_BASE_URL}/auth/login', json={
                'username': username, 
                'password': password,
                'remember': remember
            })
            
            if response.status_code == 200:
                data = response.json()['data']
                session['access_token'] = data['access_token']
                session['refresh_token'] = data['refresh_token']
                session['user_id'] = data['user']['id']
                session['user_role'] = data['user']['role']
                session['user_name'] = data['user']['full_name']
                
                flash('Login successful!', 'success')
                
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
        
        if request.form.get('age'):
            try:
                age = int(request.form.get('age'))
                if age < 13 or age > 120:
                    field_errors['age'] = 'Age must be between 13 and 120'
            except ValueError:
                field_errors['age'] = 'Please enter a valid age'
        
        if field_errors:
            return render_template('auth/register.html', field_errors=field_errors)
        
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
                login_response = requests.post(f'{API_BASE_URL}/auth/login', json={
                    'username': data['username'],
                    'password': data['password'],
                    'remember': False
                })
                
                if login_response.status_code == 200:
                    login_data = login_response.json()['data']
                    session['access_token'] = login_data['access_token']
                    session['refresh_token'] = login_data['refresh_token']
                    session['user_id'] = login_data['user']['id']
                    session['user_role'] = login_data['user']['role']
                    session['user_name'] = login_data['user']['full_name']
                    
                    flash('Registration successful! Welcome to EduPlatform!', 'success')
                    
                    if login_data['user']['role'] == 'admin':
                        return redirect(url_for('frontend.admin_dashboard'))
                    elif login_data['user']['role'] == 'teacher':
                        return redirect(url_for('frontend.teacher_dashboard'))
                    else:
                        return redirect(url_for('frontend.student_dashboard'))
                else:
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
        return redirect(url_for('frontend.index'))
    
    try:
        headers = get_auth_headers()
        response = requests.get(f'{API_BASE_URL}/admin/dashboard', headers=headers)
        
        if response.status_code == 200:
            response_data = response.json()
            dashboard_data = response_data.get('data', {})
            return render_template('admin/dashboard.html', data=dashboard_data)
        else:
            flash('Failed to load dashboard data', 'error')
            return render_template('admin/dashboard.html', data={
                'users': {'total': 0, 'students': 0, 'teachers': 0, 'active': 0, 'recent': 0},
                'courses': {'total': 0, 'published': 0, 'recent': 0},
                'enrollments': {'total': 0, 'active': 0, 'completed': 0, 'recent': 0},
                'quizzes': {'total': 0, 'attempts': 0}
            })
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('admin/dashboard.html', data={
            'users': {'total': 0, 'students': 0, 'teachers': 0, 'active': 0, 'recent': 0},
            'courses': {'total': 0, 'published': 0, 'recent': 0},
            'enrollments': {'total': 0, 'active': 0, 'completed': 0, 'recent': 0},
            'quizzes': {'total': 0, 'attempts': 0}
        })

@bp.route('/admin/users')
def admin_users():
    """Admin users management"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('frontend.index'))
    
    page = request.args.get('page', 1, type=int)
    role = request.args.get('role', '')
    status = request.args.get('status', '')
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
            
        response = requests.get(f'{API_BASE_URL}/admin/users', headers=headers, params=params)
        
        if response.status_code == 200:
            users_data = response.json()
            return render_template('admin/users.html', 
                                 users=users_data.get('users', []),
                                 total=users_data.get('total', 0),
                                 page=page,
                                 pages=users_data.get('pages', 1),
                                 current_role=role,
                                 current_status=status,
                                 current_search=search)
        else:
            flash('Failed to load users data', 'error')
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
    """Admin courses management"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('frontend.index'))
    
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '')
    status = request.args.get('status', '')
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
            
        response = requests.get(f'{API_BASE_URL}/admin/courses', headers=headers, params=params)
        
        if response.status_code == 200:
            courses_data = response.json()
            return render_template('admin/courses.html', 
                                 courses=courses_data.get('courses', []),
                                 total=courses_data.get('total', 0),
                                 page=page,
                                 pages=courses_data.get('pages', 1),
                                 current_category=category,
                                 current_status=status,
                                 current_search=search)
        else:
            flash('Failed to load courses data', 'error')
            return render_template('admin/courses.html', 
                                 courses=[], total=0, page=1, pages=1,
                                 current_category=category, current_status=status, current_search=search)
    except Exception as e:
        flash(f'Error loading courses: {str(e)}', 'error')
        return render_template('admin/courses.html', 
                             courses=[], total=0, page=1, pages=1,
                             current_category=category, current_status=status, current_search=search)

@bp.route('/admin/reports')
def admin_reports():
    """Admin reports page"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('frontend.index'))
    
    days = request.args.get('days', 30, type=int)
    
    try:
        headers = get_auth_headers()
        
        activity_response = requests.get(
            f'{API_BASE_URL}/admin/reports/user-activity',
            headers=headers,
            params={'days': days}
        )
        
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
        
        if performance_response.status_code == 200:
            performance_data = performance_response.json()
        else:
            performance_data = {
                'courses': [],
                'total_courses': 0
            }
        
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
            error_data = response.json()
            return jsonify({'error': error_data.get('error', 'Failed to toggle user status')}), response.status_code
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
            error_data = response.json()
            return jsonify({'error': error_data.get('error', 'Failed to load user details')}), response.status_code
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
            error_data = response.json()
            return jsonify({'error': error_data.get('error', 'Failed to update user')}), response.status_code
    except Exception as e:
        return jsonify({'error': f'Connection error: {str(e)}'}), 500

@bp.route('/admin/users/export')
def export_users():
    """Export users to CSV"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('frontend.index'))
    
    try:
        headers = get_auth_headers()
        
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
            error_data = response.json()
            return jsonify({'error': error_data.get('error', 'Failed to toggle course status')}), response.status_code
    except Exception as e:
        return jsonify({'error': f'Connection error: {str(e)}'}), 500

@bp.route('/admin/courses/<int:course_id>/details', methods=['GET'])
def get_course_details(course_id):
    """Get course details for viewing - NEW"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        headers = get_auth_headers()
        response = requests.get(f'{API_BASE_URL}/courses/{course_id}', headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            error_data = response.json()
            return jsonify({'error': error_data.get('error', 'Failed to load course details')}), response.status_code
    except Exception as e:
        return jsonify({'error': f'Connection error: {str(e)}'}), 500

@bp.route('/admin/courses/export')
def export_courses():
    """Export courses to CSV"""
    if not session.get('access_token') or session.get('user_role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('frontend.index'))
    
    try:
        headers = get_auth_headers()
        
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

@bp.route('/profile')
def profile():
    """User profile page"""
    if not session.get('access_token'):
        flash('Please log in to access your profile.', 'error')
        return redirect(url_for('frontend.index'))
    
    return render_template('profile.html')

@bp.route('/profile/update', methods=['POST'])
def update_profile():
    """Update user profile - AJAX endpoint"""
    if not session.get('access_token'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        headers = get_auth_headers()
        data = request.get_json()
        
        response = requests.put(f'{API_BASE_URL}/auth/profile', 
                              headers=headers, 
                              json=data)
        
        if response.status_code == 200:
            result = response.json()
            if 'data' in result and 'user' in result['data']:
                session['user_name'] = result['data']['user']['full_name']
            return jsonify(result)
        else:
            error_data = response.json()
            return jsonify(error_data), response.status_code
    except Exception as e:
        return jsonify({'error': f'Connection error: {str(e)}'}), 500

@bp.route('/profile/change-password', methods=['POST'])
def change_password():
    """Change user password - AJAX endpoint"""
    if not session.get('access_token'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        headers = get_auth_headers()
        data = request.get_json()
        
        response = requests.post(f'{API_BASE_URL}/auth/change-password', 
                               headers=headers, 
                               json=data)
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            error_data = response.json()
            return jsonify(error_data), response.status_code
    except Exception as e:
        return jsonify({'error': f'Connection error: {str(e)}'}), 500

@bp.route('/student/dashboard')
def student_dashboard():
    """Student dashboard (placeholder)"""
    if not session.get('access_token') or session.get('user_role') != 'student':
        flash('Access denied. Student privileges required.', 'error')
        return redirect(url_for('frontend.index'))
    
    return render_template('student/dashboard.html')

@bp.route('/teacher/dashboard')
def teacher_dashboard():
    """Teacher dashboard"""
    if not session.get('access_token') or session.get('user_role') != 'teacher':
        flash('Access denied. Teacher privileges required.', 'error')
        return redirect(url_for('frontend.index'))
    
    return render_template('teacher/dashboard.html')

@bp.route('/teacher/courses')
def teacher_courses():
    """Teacher courses management"""
    if not session.get('access_token') or session.get('user_role') != 'teacher':
        flash('Access denied. Teacher privileges required.', 'error')
        return redirect(url_for('frontend.index'))
    
    return render_template('teacher/courses.html')

@bp.route('/teacher/courses/create')
def teacher_create_course():
    """Create new course page"""
    if not session.get('access_token') or session.get('user_role') != 'teacher':
        flash('Access denied. Teacher privileges required.', 'error')
        return redirect(url_for('frontend.index'))
    
    return render_template('teacher/create_course.html')

@bp.route('/teacher/courses/<int:course_id>')
def teacher_course_view(course_id):
    """View specific course - redirects to content management"""
    if not session.get('access_token') or session.get('user_role') != 'teacher':
        flash('Access denied. Teacher privileges required.', 'error')
        return redirect(url_for('frontend.index'))
    
    return redirect(url_for('frontend.teacher_course_content', course_id=course_id))

@bp.route('/teacher/courses/<int:course_id>/content')
def teacher_course_content(course_id):
    """Manage course content"""
    if not session.get('access_token') or session.get('user_role') != 'teacher':
        flash('Access denied. Teacher privileges required.', 'error')
        return redirect(url_for('frontend.index'))
    
    return render_template('teacher/course_content.html', course_id=course_id)

@bp.route('/teacher/courses/<int:course_id>/analytics')
def teacher_course_analytics(course_id):
    """Course analytics"""
    if not session.get('access_token') or session.get('user_role') != 'teacher':
        flash('Access denied. Teacher privileges required.', 'error')
        return redirect(url_for('frontend.index'))
    
    return render_template('teacher/course_analytics.html', course_id=course_id)

@bp.route('/teacher/courses/<int:course_id>/students')
def teacher_course_students(course_id):
    """Course students management"""
    if not session.get('access_token') or session.get('user_role') != 'teacher':
        flash('Access denied. Teacher privileges required.', 'error')
        return redirect(url_for('frontend.index'))
    
    return render_template('teacher/course_students.html', course_id=course_id)

@bp.route('/teacher/submissions')
def teacher_submissions():
    """Pending submissions for grading"""
    if not session.get('access_token') or session.get('user_role') != 'teacher':
        flash('Access denied. Teacher privileges required.', 'error')
        return redirect(url_for('frontend.index'))
    
    return render_template('teacher/submissions.html')

@bp.route('/teacher/analytics')
def teacher_analytics():
    """Teacher analytics overview"""
    if not session.get('access_token') or session.get('user_role') != 'teacher':
        flash('Access denied. Teacher privileges required.', 'error')
        return redirect(url_for('frontend.index'))
    
    return render_template('teacher/analytics.html')

@bp.route('/teacher/lesson/<int:lesson_id>/preview')
def teacher_lesson_preview(lesson_id):
    """Preview a lesson"""
    if not session.get('access_token') or session.get('user_role') != 'teacher':
        flash('Access denied. Teacher privileges required.', 'error')
        return redirect(url_for('frontend.index'))
    
    return render_template('teacher/lesson_preview.html', lesson_id=lesson_id)

@bp.route('/teacher/quiz/<int:quiz_id>/analytics')
def teacher_quiz_analytics(quiz_id):
    """Quiz analytics"""
    if not session.get('access_token') or session.get('user_role') != 'teacher':
        flash('Access denied. Teacher privileges required.', 'error')
        return redirect(url_for('frontend.index'))
    
    return render_template('teacher/quiz_analytics.html', quiz_id=quiz_id)

@bp.route('/teacher/quiz/<int:quiz_id>/questions')
def teacher_quiz_questions(quiz_id):
    """Manage quiz questions"""
    if not session.get('access_token') or session.get('user_role') != 'teacher':
        flash('Access denied. Teacher privileges required.', 'error')
        return redirect(url_for('frontend.index'))
    
    return render_template('teacher/quiz_questions.html', quiz_id=quiz_id)

@bp.route('/teacher/assignment/<int:assignment_id>/submissions')
def teacher_assignment_submissions(assignment_id):
    """View assignment submissions"""
    if not session.get('access_token') or session.get('user_role') != 'teacher':
        flash('Access denied. Teacher privileges required.', 'error')
        return redirect(url_for('frontend.index'))
    
    return render_template('teacher/assignment_submissions.html', assignment_id=assignment_id)

@bp.route('/messages')
def messages():
    """Messages inbox page"""
    if not session.get('access_token'):
        flash('Please log in to access messages.', 'error')
        return redirect(url_for('frontend.index'))
    
    return render_template('messages/inbox.html')

@bp.route('/messages/compose')
def compose_message():
    """Compose new message page"""
    if not session.get('access_token'):
        flash('Please log in to compose messages.', 'error')
        return redirect(url_for('frontend.index'))
    
    return render_template('messages/compose.html')

@bp.route('/messages/conversation/<int:partner_id>')
def message_conversation(partner_id):
    """View conversation with specific user"""
    if not session.get('access_token'):
        flash('Please log in to view conversations.', 'error')
        return redirect(url_for('frontend.index'))
    
    return render_template('messages/conversation.html', partner_id=partner_id)

@bp.route('/teacher/student/<int:student_id>/progress')
def teacher_student_progress(student_id):
    """View individual student progress"""
    if not session.get('access_token') or session.get('user_role') != 'teacher':
        flash('Access denied. Teacher privileges required.', 'error')
        return redirect(url_for('frontend.index'))
    
    course_id = request.args.get('course', type=int)
    if not course_id:
        flash('Course ID is required.', 'error')
        return redirect(url_for('frontend.teacher_courses'))
    
    return render_template('teacher/student_progress.html', student_id=student_id, course_id=course_id)