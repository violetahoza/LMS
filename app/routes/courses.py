from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from sqlalchemy import or_

from app.models import db, User, Course, Enrollment, UserRole
from app.utils.decorators import teacher_required

bp = Blueprint('courses', __name__, url_prefix='/api/courses')

@bp.route('/', methods=['GET'])
@jwt_required()
def get_courses():
    """Get all courses (filtered based on user role)"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        category = request.args.get('category')
        search = request.args.get('search')
        
        # Base query
        query = Course.query
        
        # Filter based on user role
        if user.is_teacher():
            # Teachers see their own courses
            query = query.filter_by(teacher_id=user_id)
        elif user.is_student():
            # Students see only published courses
            query = query.filter_by(is_published=True)
        
        # Apply filters
        if category:
            query = query.filter_by(category=category)
        
        if search:
            query = query.filter(
                or_(
                    Course.title.contains(search),
                    Course.description.contains(search)
                )
            )
        
        # Paginate results
        pagination = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        courses = [course.to_dict() for course in pagination.items]
        
        # Add enrollment status for students
        if user.is_student():
            enrollments = Enrollment.query.filter_by(student_id=user_id).all()
            enrolled_course_ids = {e.course_id for e in enrollments}
            
            for course in courses:
                course['is_enrolled'] = course['id'] in enrolled_course_ids
        
        return jsonify({
            'courses': courses,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:course_id>', methods=['GET'])
@jwt_required()
def get_course(course_id):
    """Get a specific course"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        course = Course.query.get(course_id)
        
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        # Check permissions
        if not course.is_published and not user.can_access_course(course):
            return jsonify({'error': 'Access denied'}), 403
        
        course_data = course.to_dict()
        
        # Add additional info based on user role
        if user.is_student():
            enrollment = Enrollment.query.filter_by(
                student_id=user_id, 
                course_id=course_id
            ).first()
            course_data['is_enrolled'] = enrollment is not None
            if enrollment:
                course_data['enrollment'] = enrollment.to_dict()
        
        # Add lesson count
        course_data['lesson_count'] = course.lessons.count()
        course_data['quiz_count'] = course.quizzes.count()
        course_data['assignment_count'] = course.assignments.count()
        
        return jsonify(course_data), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/', methods=['POST'])
@teacher_required()
def create_course():
    """Create a new course (teachers only)"""
    try:
        data = request.get_json()
        user_id = get_jwt_identity()
        
        # Validate required fields
        required_fields = ['title', 'description']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Create new course
        course = Course(
            title=data['title'],
            description=data['description'],
            category=data.get('category'),
            teacher_id=user_id,
            start_date=datetime.fromisoformat(data['start_date']) if data.get('start_date') else None,
            end_date=datetime.fromisoformat(data['end_date']) if data.get('end_date') else None,
            max_students=data.get('max_students', 50),
            is_published=data.get('is_published', False)
        )
        
        db.session.add(course)
        db.session.commit()
        
        return jsonify({
            'message': 'Course created successfully',
            'course': course.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:course_id>', methods=['PUT'])
@teacher_required()
def update_course(course_id):
    """Update a course (teachers only)"""
    try:
        data = request.get_json()
        user_id = get_jwt_identity()
        course = Course.query.get(course_id)
        
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        # Check ownership
        if course.teacher_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Update allowed fields
        allowed_fields = ['title', 'description', 'category', 'max_students', 'is_published']
        for field in allowed_fields:
            if field in data:
                setattr(course, field, data[field])
        
        # Update dates
        if 'start_date' in data:
            course.start_date = datetime.fromisoformat(data['start_date']) if data['start_date'] else None
        if 'end_date' in data:
            course.end_date = datetime.fromisoformat(data['end_date']) if data['end_date'] else None
        
        course.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Course updated successfully',
            'course': course.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:course_id>', methods=['DELETE'])
@teacher_required()
def delete_course(course_id):
    """Delete a course (teachers only)"""
    try:
        user_id = get_jwt_identity()
        course = Course.query.get(course_id)
        
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        # Check ownership
        if course.teacher_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Check if course has active enrollments
        active_enrollments = course.enrollments.filter_by(status='active').count()
        if active_enrollments > 0:
            return jsonify({
                'error': f'Cannot delete course with {active_enrollments} active enrollments'
            }), 400
        
        db.session.delete(course)
        db.session.commit()
        
        return jsonify({'message': 'Course deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:course_id>/enroll', methods=['POST'])
@jwt_required()
def enroll_in_course(course_id):
    """Enroll in a course (students only)"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user.is_student():
            return jsonify({'error': 'Only students can enroll in courses'}), 403
        
        course = Course.query.get(course_id)
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        if not course.is_published:
            return jsonify({'error': 'Course is not published'}), 400
        
        # Check if already enrolled
        existing_enrollment = Enrollment.query.filter_by(
            student_id=user_id,
            course_id=course_id
        ).first()
        
        if existing_enrollment:
            if existing_enrollment.status == 'active':
                return jsonify({'error': 'Already enrolled in this course'}), 400
            elif existing_enrollment.status == 'dropped':
                # Re-enroll
                existing_enrollment.status = 'active'
                existing_enrollment.enrolled_at = datetime.utcnow()
                db.session.commit()
                return jsonify({
                    'message': 'Re-enrolled in course successfully',
                    'enrollment': existing_enrollment.to_dict()
                }), 200
        
        # Check if course is full
        if course.is_full():
            return jsonify({'error': 'Course is full'}), 400
        
        # Create new enrollment
        enrollment = Enrollment(
            student_id=user_id,
            course_id=course_id,
            status='active'
        )
        
        db.session.add(enrollment)
        db.session.commit()
        
        return jsonify({
            'message': 'Enrolled in course successfully',
            'enrollment': enrollment.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:course_id>/drop', methods=['POST'])
@jwt_required()
def drop_course(course_id):
    """Drop a course (students only)"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user.is_student():
            return jsonify({'error': 'Only students can drop courses'}), 403
        
        enrollment = Enrollment.query.filter_by(
            student_id=user_id,
            course_id=course_id,
            status='active'
        ).first()
        
        if not enrollment:
            return jsonify({'error': 'Not enrolled in this course'}), 404
        
        enrollment.status = 'dropped'
        db.session.commit()
        
        return jsonify({'message': 'Course dropped successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/enrolled', methods=['GET'])
@jwt_required()
def get_enrolled_courses():
    """Get courses the student is enrolled in"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user.is_student():
            return jsonify({'error': 'Only students can access enrolled courses'}), 403
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', 'active')
        
        # Get enrollments
        query = Enrollment.query.filter_by(student_id=user_id)
        
        if status:
            query = query.filter_by(status=status)
        
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        enrollments = []
        for enrollment in pagination.items:
            enrollment_data = enrollment.to_dict()
            enrollment_data['course'] = enrollment.course.to_dict()
            enrollments.append(enrollment_data)
        
        return jsonify({
            'enrollments': enrollments,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:course_id>/students', methods=['GET'])
@teacher_required()
def get_course_students(course_id):
    """Get students enrolled in a course (teachers only)"""
    try:
        user_id = get_jwt_identity()
        course = Course.query.get(course_id)
        
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        # Check ownership
        if course.teacher_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get enrollments
        enrollments = Enrollment.query.filter_by(
            course_id=course_id,
            status='active'
        ).all()
        
        students = []
        for enrollment in enrollments:
            student_data = enrollment.student.to_dict()
            student_data['enrollment'] = enrollment.to_dict()
            students.append(student_data)
        
        return jsonify({
            'students': students,
            'total': len(students)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500