from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy import or_, desc
from app.models import db, User, Message, Course, Enrollment
from app.utils.base_controller import ValidationException, PermissionException, NotFoundException
from app.services.notification_service import NotificationService

class MessagingService:
    """Service for messaging functionality"""
    
    @staticmethod
    def send_message(sender_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message"""
        sender = User.query.get(sender_id)
        if not sender:
            raise NotFoundException("Sender not found")
        
        recipient_id = data.get('recipient_id')
        subject = data.get('subject', '').strip()
        content = data.get('content', '').strip()
        course_id = data.get('course_id')
        
        if not recipient_id or not subject or not content:
            raise ValidationException("Recipient, subject, and content are required")
        
        recipient = User.query.get(recipient_id)
        if not recipient:
            raise ValidationException("Recipient not found")
        
        if not MessagingService._can_message(sender, recipient, course_id):
            raise PermissionException("You cannot send messages to this user")
        
        message = Message(
            sender_id=sender_id,
            recipient_id=recipient_id,
            course_id=course_id,
            subject=subject,
            content=content
        )
        
        db.session.add(message)
        db.session.commit()
        
        try:
            NotificationService.notify_new_message(sender_id, recipient_id, subject)
        except Exception as e:
            print(f"Failed to send notification: {e}")
                    
        return {
            'message': 'Message sent successfully',
            'message_data': message.to_dict()
        }
    
    @staticmethod
    def get_messages(user_id: int, message_type: str = 'received', page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Get messages for a user"""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundException("User not found")
        
        if message_type == 'received':
            query = Message.query.filter_by(recipient_id=user_id)
        elif message_type == 'sent':
            query = Message.query.filter_by(sender_id=user_id)
        else:
            query = Message.query.filter(
                or_(Message.sender_id == user_id, Message.recipient_id == user_id)
            )
        
        pagination = query.order_by(desc(Message.sent_at)).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        messages = [message.to_dict() for message in pagination.items]
        
        return {
            'messages': messages,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages,
            'unread_count': Message.query.filter_by(
                recipient_id=user_id,
                read_at=None
            ).count() if message_type == 'received' else 0
        }
    
    @staticmethod
    def get_message(user_id: int, message_id: int) -> Dict[str, Any]:
        """Get a specific message"""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundException("User not found")
        
        message = Message.query.get(message_id)
        if not message:
            raise NotFoundException("Message not found")
        
        if message.sender_id != user_id and message.recipient_id != user_id:
            raise PermissionException("Access denied")
        
        if message.recipient_id == user_id and message.read_at is None:
            message.read_at = datetime.utcnow()
            db.session.commit()
        
        return message.to_dict()
    
    @staticmethod
    def mark_as_read(user_id: int, message_id: int) -> Dict[str, str]:
        """Mark a message as read"""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundException("User not found")
        
        message = Message.query.get(message_id)
        if not message:
            raise NotFoundException("Message not found")
        
        if message.recipient_id != user_id:
            raise PermissionException("Access denied")
        
        if message.read_at is None:
            message.read_at = datetime.utcnow()
            db.session.commit()
        
        return {'message': 'Message marked as read'}
    
    @staticmethod
    def get_conversations(user_id: int) -> Dict[str, Any]:
        """Get conversations for a user"""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundException("User not found")
        
        sent_to = db.session.query(Message.recipient_id).filter_by(sender_id=user_id).distinct().subquery()
        received_from = db.session.query(Message.sender_id).filter_by(recipient_id=user_id).distinct().subquery()
        
        conversation_partners = db.session.query(User).filter(
            or_(
                User.id.in_(sent_to),
                User.id.in_(received_from)
            )
        ).all()
        
        conversations = []
        for partner in conversation_partners:
            latest_message = Message.query.filter(
                or_(
                    db.and_(Message.sender_id == user_id, Message.recipient_id == partner.id),
                    db.and_(Message.sender_id == partner.id, Message.recipient_id == user_id)
                )
            ).order_by(desc(Message.sent_at)).first()
            
            unread_count = Message.query.filter_by(
                sender_id=partner.id,
                recipient_id=user_id,
                read_at=None
            ).count()
            
            if latest_message:
                conversations.append({
                    'partner': partner.to_dict(),
                    'latest_message': latest_message.to_dict(),
                    'unread_count': unread_count
                })
        
        conversations.sort(key=lambda x: x['latest_message']['sent_at'], reverse=True)
        
        return {
            'conversations': conversations,
            'total': len(conversations)
        }
    
    @staticmethod
    def get_conversation_messages(user_id: int, partner_id: int, page: int = 1, per_page: int = 50) -> Dict[str, Any]:
        """Get messages in a conversation between two users"""
        user = User.query.get(user_id)
        partner = User.query.get(partner_id)
        
        if not user or not partner:
            raise NotFoundException("User not found")
        
        query = Message.query.filter(
            or_(
                db.and_(Message.sender_id == user_id, Message.recipient_id == partner_id),
                db.and_(Message.sender_id == partner_id, Message.recipient_id == user_id)
            )
        )
        
        pagination = query.order_by(desc(Message.sent_at)).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        messages = [message.to_dict() for message in pagination.items]
        
        unread_messages = Message.query.filter_by(
            sender_id=partner_id,
            recipient_id=user_id,
            read_at=None
        ).all()
        
        for message in unread_messages:
            message.read_at = datetime.utcnow()
        
        if unread_messages:
            db.session.commit()
        
        return {
            'messages': messages,
            'partner': partner.to_dict(),
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }
    
    @staticmethod
    def _can_message(sender: User, recipient: User, course_id: int = None) -> bool:
        """Check if sender can message recipient"""
        if sender.is_admin():
            return True
        
        existing_conversation = Message.query.filter(
            or_(
                db.and_(Message.sender_id == sender.id, Message.recipient_id == recipient.id),
                db.and_(Message.sender_id == recipient.id, Message.recipient_id == sender.id)
            )
        ).first()
        
        if existing_conversation:
            return True
        
        if course_id:
            course = Course.query.get(course_id)
            if not course:
                return False
            
            if sender.is_teacher() and course.teacher_id == sender.id and recipient.is_student():
                enrollment = Enrollment.query.filter_by(
                    student_id=recipient.id,
                    course_id=course_id
                ).first()
                return enrollment is not None
            
            if sender.is_student() and recipient.is_teacher() and course.teacher_id == recipient.id:
                enrollment = Enrollment.query.filter_by(
                    student_id=sender.id,
                    course_id=course_id
                ).first()
                return enrollment is not None
        
        
        if sender.is_teacher() and recipient.is_admin():
            return True
        
        if sender.is_student() and recipient.is_admin():
            return True
        
        if sender.is_teacher() and recipient.is_teacher():
            return True
        
        if sender.is_teacher() and recipient.is_student():
            shared_courses = Course.query.filter_by(teacher_id=sender.id).join(
                Enrollment, Course.id == Enrollment.course_id
            ).filter_by(student_id=recipient.id).first()
            return shared_courses is not None
        
        if sender.is_student() and recipient.is_teacher():
            shared_courses = Course.query.filter_by(teacher_id=recipient.id).join(
                Enrollment, Course.id == Enrollment.course_id
            ).filter_by(student_id=sender.id, status='active').first()
            return shared_courses is not None
        
        if sender.is_student() and recipient.is_student():
            return False
        
        return False