from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from app.models import db, User, Course, Lesson, LessonProgress, Enrollment
from app.utils.decorators import teacher_required

bp = Blueprint('lessons', __name__, url_prefix='/api/lessons')

@bp.route('/course/<int:course_id>', methods=['GET'])
@jwt_required()
def get_course_lessons(course_id):
    """Get all lessons for a course"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        course = Course.query.get(course_id)
        
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        # Check access permissions
        if not user.can_access_course(course):
            return jsonify({'error': 'Access denied'}), 403
        
        # Get lessons ordered by order_number
        lessons = course.lessons.order_by(Lesson.order_number).all()
        lessons_data = []
        
        for lesson in lessons:
            lesson_dict = lesson.to_dict()
            
            # Add progress info for students
            if user.is_student():
                progress = LessonProgress.query.filter_by(
                    student_id=user_id,
                    lesson_id=lesson.id
                ).first()
                
                lesson_dict['progress'] = {
                    'viewed': progress is not None,
                    'completed': progress.completed_at is not None if progress else False,
                    'time_spent_minutes': progress.time_spent_minutes if progress else 0
                }
            
            lessons_data.append(lesson_dict)
        
        return jsonify({
            'lessons': lessons_data,
            'total': len(lessons_data)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:lesson_id>', methods=['GET'])
@jwt_required()
def get_lesson(lesson_id):
    """Get a specific lesson"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        lesson = Lesson.query.get(lesson_id)
        
        if not lesson:
            return jsonify({'error': 'Lesson not found'}), 404
        
        # Check access permissions
        if not user.can_access_course(lesson.course):
            return jsonify({'error': 'Access denied'}), 403
        
        lesson_data = lesson.to_dict()
        
        # Track lesson view for students
        if user.is_student():
            progress = LessonProgress.query.filter_by(
                student_id=user_id,
                lesson_id=lesson_id
            ).first()
            
            if not progress:
                progress = LessonProgress(
                    student_id=user_id,
                    lesson_id=lesson_id
                )
                db.session.add(progress)
            else:
                progress.viewed_at = datetime.utcnow()
            
            db.session.commit()
            
            lesson_data['progress'] = {
                'viewed': True,
                'completed': progress.completed_at is not None,
                'time_spent_minutes': progress.time_spent_minutes
            }
        
        return jsonify(lesson_data), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/', methods=['POST'])
@teacher_required()
def create_lesson():
    """Create a new lesson"""
    try:
        data = request.get_json()
        user_id = get_jwt_identity()
        
        # Validate required fields
        required_fields = ['course_id', 'title', 'content', 'order_number']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check course ownership
        course = Course.query.get(data['course_id'])
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        if course.teacher_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Create lesson
        lesson = Lesson(
            course_id=data['course_id'],
            title=data['title'],
            content=data['content'],
            order_number=data['order_number'],
            lesson_type=data.get('lesson_type', 'text'),
            video_url=data.get('video_url'),
            duration_minutes=data.get('duration_minutes')
        )
        
        db.session.add(lesson)
        db.session.commit()
        
        return jsonify({
            'message': 'Lesson created successfully',
            'lesson': lesson.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:lesson_id>', methods=['PUT'])
@teacher_required()
def update_lesson(lesson_id):
    """Update a lesson"""
    try:
        data = request.get_json()
        user_id = get_jwt_identity()
        lesson = Lesson.query.get(lesson_id)
        
        if not lesson:
            return jsonify({'error': 'Lesson not found'}), 404
        
        # Check ownership
        if lesson.course.teacher_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Update fields
        allowed_fields = ['title', 'content', 'order_number', 'lesson_type', 'video_url', 'duration_minutes']
        for field in allowed_fields:
            if field in data:
                setattr(lesson, field, data[field])
        
        lesson.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Lesson updated successfully',
            'lesson': lesson.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:lesson_id>', methods=['DELETE'])
@teacher_required()
def delete_lesson(lesson_id):
    """Delete a lesson"""
    try:
        user_id = get_jwt_identity()
        lesson = Lesson.query.get(lesson_id)
        
        if not lesson:
            return jsonify({'error': 'Lesson not found'}), 404
        
        # Check ownership
        if lesson.course.teacher_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        db.session.delete(lesson)
        db.session.commit()
        
        return jsonify({'message': 'Lesson deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:lesson_id>/complete', methods=['POST'])
@jwt_required()
def complete_lesson(lesson_id):
    """Mark a lesson as complete"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user.is_student():
            return jsonify({'error': 'Only students can complete lessons'}), 403
        
        lesson = Lesson.query.get(lesson_id)
        if not lesson:
            return jsonify({'error': 'Lesson not found'}), 404
        
        # Check enrollment
        enrollment = Enrollment.query.filter_by(
            student_id=user_id,
            course_id=lesson.course_id,
            status='active'
        ).first()
        
        if not enrollment:
            return jsonify({'error': 'Not enrolled in this course'}), 403
        
        # Update or create progress
        progress = LessonProgress.query.filter_by(
            student_id=user_id,
            lesson_id=lesson_id
        ).first()
        
        if not progress:
            progress = LessonProgress(
                student_id=user_id,
                lesson_id=lesson_id
            )
            db.session.add(progress)
        
        progress.completed_at = datetime.utcnow()
        
        # Update time spent if provided
        data = request.get_json()
        if data and 'time_spent_minutes' in data:
            progress.time_spent_minutes = data['time_spent_minutes']
        
        # Update course progress
        enrollment.progress_percentage = enrollment.calculate_progress()
        
        # Check if course is completed
        total_lessons = lesson.course.lessons.count()
        completed_lessons = LessonProgress.query.filter_by(
            student_id=user_id
        ).join(Lesson).filter(
            Lesson.course_id == lesson.course_id,
            LessonProgress.completed_at.isnot(None)
        ).count()
        
        if completed_lessons == total_lessons:
            enrollment.status = 'completed'
            enrollment.completed_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Lesson marked as complete',
            'progress': {
                'lesson_completed': True,
                'course_progress': enrollment.progress_percentage,
                'course_completed': enrollment.status == 'completed'
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500