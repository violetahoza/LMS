from flask import jsonify
from app.models import db
import logging
import traceback

logger = logging.getLogger(__name__)

class BaseController:
    """Base controller with common request handling patterns"""
    
    @staticmethod
    def handle_request(service_method, *args, success_message="Success", success_code=200, **kwargs):
        """Generic request handler with error handling"""
        try:
            result = service_method(*args, **kwargs)
            
            if isinstance(result, dict) and 'message' in result:
                return jsonify(result), success_code
            
            return jsonify({
                'message': success_message,
                'data': result
            }), success_code
            
        except ValidationException as e:
            logger.warning(f"Validation error: {str(e)}")
            return jsonify({'error': str(e)}), 400
        except PermissionException as e:
            logger.warning(f"Permission error: {str(e)}")
            return jsonify({'error': str(e)}), 403
        except NotFoundException as e:
            logger.warning(f"Not found error: {str(e)}")
            return jsonify({'error': str(e)}), 404
        except ValueError as e:
            logger.warning(f"Value error: {str(e)}")
            return jsonify({'error': str(e)}), 400
        except PermissionError as e:
            logger.warning(f"Permission error: {str(e)}")
            return jsonify({'error': str(e)}), 403
        except FileNotFoundError as e:
            logger.warning(f"Not found error: {str(e)}")
            return jsonify({'error': str(e)}), 404
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            db.session.rollback()
            return jsonify({'error': 'Internal server error'}), 500
    
    @staticmethod
    def handle_list_request(service_method, *args, **kwargs):
        """Handle paginated list requests"""
        try:
            result = service_method(*args, **kwargs)
            return jsonify(result), 200
        except ValidationException as e:
            logger.warning(f"Validation error: {str(e)}")
            return jsonify({'error': str(e)}), 400
        except PermissionException as e:
            logger.warning(f"Permission error: {str(e)}")
            return jsonify({'error': str(e)}), 403
        except NotFoundException as e:
            logger.warning(f"Not found error: {str(e)}")
            return jsonify({'error': str(e)}), 404
        except Exception as e:
            logger.error(f"List request error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return jsonify({'error': 'Internal server error'}), 500

class ServiceException(Exception):
    """Base exception for service layer"""
    pass

class ValidationException(ServiceException):
    """Raised when validation fails"""
    pass

class PermissionException(ServiceException):
    """Raised when user lacks permission"""
    pass

class NotFoundException(ServiceException):
    """Raised when resource not found"""
    pass