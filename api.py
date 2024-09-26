from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
import os
import hashlib
import hmac
from urllib.parse import parse_qsl
import logging
from functools import wraps
from config import service_manager, storage_client  # Import storage_client from config
import json

# Configure logging
logger = logging.getLogger(__name__)

# Define the Blueprint
api_blueprint = Blueprint('api', __name__)

def validate_init_data(init_data: str, bot_token: str) -> tuple[dict, bool]:
    """
    Validate the init data received from Telegram Mini App.
    """
    # Step 1: Parse the query string and create an array of "key=value" strings
    parsed_data = dict(parse_qsl(init_data, keep_blank_values=True))
    hash_value = parsed_data.pop('hash', '')
    data_check_array = [f"{k}={v}" for k, v in parsed_data.items()]
        
    # Step 2: Sort the array in alphabetical order
    data_check_array.sort()
        
    # Join the array elements with newline character
    data_check_string = '\n'.join(data_check_array)
        
    # Step 3: Create HMAC-SHA256 secret key
    secret_key = hmac.new('WebAppData'.encode(), bot_token.encode(), hashlib.sha256).digest()
        
    # Step 4: Create HMAC-SHA256 hash of the data string
    data_check_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
    # Step 5 & 6: Compare the calculated hash with the provided hash
    return (parsed_data, hmac.compare_digest(data_check_hash, hash_value))

def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')

        if not auth_header or not auth_header.startswith('tma '):
            return jsonify({"error": "Missing or invalid Authorization header"}), 400

        init_data = auth_header[4:]  # Remove 'tma ' prefix

        if not bot_token:
            return jsonify({"error": "Bot token not configured"}), 500

        try:
            logger.info(f"Validating init data: {init_data}")
            parsed_data, is_valid = validate_init_data(init_data, bot_token)
            logger.info(f"Init data validation result: {is_valid}, parsed data: {parsed_data}")
            
            if not is_valid:
                return jsonify({"valid": False}), 400

            try:
                start_param = int(parsed_data.get('start_param', ''))
            except ValueError:
                return jsonify({"valid": False}), 400

            community = service_manager.get_community_by_chat_id(start_param)

            if not community:
                return jsonify({"valid": False}), 404

            request.parsed_data = parsed_data  # Store parsed data in request context
            request.community = community  # Store community in request context
            # Extract user information from parsed_data
            user_info_str = parsed_data.get('user', '{}')
            try:
                user_info = json.loads(user_info_str)
                request.user_info = user_info  # Store user info in request context
            except json.JSONDecodeError:
                logger.error(f"Error decoding user info: {user_info_str}")
                return jsonify({"error": "Invalid user information"}), 400

            # Extract language code, defaulting to 'en' if not present
            request.language_code = user_info.get('language_code', 'en')
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error validating init data: {str(e)}", exc_info=True)
            return jsonify({"error": str(e)}), 400

    return decorated_function

def handle_options_request(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'OPTIONS':
            return jsonify({"message": "Preflight request successful"}), 200
        return f(*args, **kwargs)
    return decorated_function

def delete_image_if_exists(entity):
    if entity and entity.get('image'):
        try:
            image_gcs_path = entity['image'].replace('https://storage.googleapis.com/', '')
            bucket_name, blob_name = image_gcs_path.split('/', 1)
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.delete()
            logger.info(f"Deleted image from GCS: {image_gcs_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting image from GCS: {str(e)}", exc_info=True)
    return False

@api_blueprint.route("/api/init", methods=['POST', 'OPTIONS'])
@token_required
def validate_telegram_init_data():
    """
    Validate the InitData received from Telegram mini app.
    """
    community = request.community
    user_info = request.user_info

    return jsonify({
        "valid": True,
        "community": {"id": community['chatId'], "name": community['name'], "language": community['language']},
        "user": {"first_name": user_info['first_name'], "last_name": user_info['last_name'], "username": user_info['username']}
    })

@api_blueprint.route("/api/theming", methods=['POST', 'OPTIONS'])
def handle_theming():
    """
    Handle theming parameters received from Telegram mini app.
    """
    logger.info(f"Received theme parameters: {request.json}")
    return jsonify({"message": "Theme parameters received successfully"}), 200

@api_blueprint.route("/api/items", methods=['GET', 'OPTIONS'])
@token_required
def search_items():
    """
    Search for items.
    """
    chat_id = request.community['chatId']  # Get chat_id from context

    try:
        items = service_manager.search_items(chat_id)
        return jsonify({"items": items})
    except Exception as e:
        logger.error(f"Error searching items: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_blueprint.route("/api/services", methods=['GET', 'OPTIONS'])
@token_required
def search_services():
    """
    Search for services.
    """
    chat_id = request.community['chatId']  # Get chat_id from context

    try:
        services = service_manager.search_services(chat_id)
        return jsonify({"services": services})
    except Exception as e:
        logger.error(f"Error searching services: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_blueprint.route("/api/events", methods=['GET', 'OPTIONS'])
@token_required
def search_events():
    """
    Search for events.
    """
    chat_id = request.community['chatId']  # Get chat_id from context

    try:
        events = service_manager.search_events(chat_id)
        return jsonify({"events": events})
    except Exception as e:
        logger.error(f"Error searching events: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_blueprint.route("/api/news", methods=['GET', 'OPTIONS'])
@token_required
def search_news():
    """
    Search for news.
    """
    chat_id = request.community['chatId']  # Get chat_id from context

    try:
        news = service_manager.search_news(chat_id)
        return jsonify({"news": news})
    except Exception as e:
        logger.error(f"Error searching news: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_blueprint.route("/api/items/<item_id>", methods=['DELETE', 'OPTIONS'])
@token_required
def delete_item(item_id):
    """
    Delete an item by its ID and its associated image if it exists.
    """
    chat_id = request.community['chatId']
    user_info = request.user_info

    try:
        deleted_item = service_manager.delete_item(item_id, chat_id, user_info['username'])
        if deleted_item:
            image_deleted = delete_image_if_exists(deleted_item)
            return jsonify({"message": "Item deleted successfully", "image_deleted": image_deleted}), 200
        else:
            return jsonify({"error": "Item not found or you don't have permission to delete it"}), 404
    except Exception as e:
        logger.error(f"Error deleting item: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_blueprint.route("/api/services/<service_id>", methods=['DELETE', 'OPTIONS'])
@token_required
def delete_service(service_id):
    """
    Delete a service by its ID and its associated image if it exists.
    """
    chat_id = request.community['chatId']
    user_info = request.user_info

    try:
        deleted_service = service_manager.delete_service(service_id, chat_id, user_info['username'])
        if deleted_service:
            image_deleted = delete_image_if_exists(deleted_service)
            return jsonify({"message": "Service deleted successfully", "image_deleted": image_deleted}), 200
        else:
            return jsonify({"error": "Service not found or you don't have permission to delete it"}), 404
    except Exception as e:
        logger.error(f"Error deleting service: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_blueprint.route("/api/events/<event_id>", methods=['DELETE', 'OPTIONS'])
@token_required
def delete_event(event_id):
    """
    Delete an event by its ID and its associated image if it exists.
    """
    chat_id = request.community['chatId']
    user_info = request.user_info

    try:
        deleted_event = service_manager.delete_event(event_id, chat_id, user_info['username'])
        if deleted_event:
            image_deleted = delete_image_if_exists(deleted_event)
            return jsonify({"message": "Event deleted successfully", "image_deleted": image_deleted}), 200
        else:
            return jsonify({"error": "Event not found or you don't have permission to delete it"}), 404
    except Exception as e:
        logger.error(f"Error deleting event: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_blueprint.route("/api/news/<news_id>", methods=['DELETE', 'OPTIONS'])
@token_required
def delete_news(news_id):
    """
    Delete a news item by its ID and its associated image if it exists.
    """
    chat_id = request.community['chatId']
    user_info = request.user_info

    try:
        deleted_news = service_manager.delete_news(news_id, chat_id, user_info['username'])
        if deleted_news:
            image_deleted = delete_image_if_exists(deleted_news)
            return jsonify({"message": "News item deleted successfully", "image_deleted": image_deleted}), 200
        else:
            return jsonify({"error": "News item not found or you don't have permission to delete it"}), 404
    except Exception as e:
        logger.error(f"Error deleting news item: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500
