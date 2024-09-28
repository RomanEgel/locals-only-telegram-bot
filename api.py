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
import requests

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

def token_required(fail_if_not_ready=True):
    def decorator(f):
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

                community = service_manager.get_community_by_id(parsed_data.get('start_param', ''))

                if not community:
                    return jsonify({"valid": False}), 404
                
                if fail_if_not_ready and community['status'] != 'READY':
                    return jsonify({"error": "Community is not ready"}), 403

                # Get chat administrators
                admins = get_chat_administrators(community['chatId'], bot_token)
                
                if admins is None:
                    return jsonify({"error": "Failed to get chat administrators"}), 500

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

                admin_usernames = [admin['user']['username'] for admin in admins if 'username' in admin['user']]
                
                request.is_admin = user_info['username'] in admin_usernames  # Store admin status in request context
                # Extract language code, defaulting to 'en' if not present
                request.language_code = user_info.get('language_code', 'en')
                return f(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error validating init data: {str(e)}", exc_info=True)
                return jsonify({"error": str(e)}), 400

        return decorated_function
    return decorator

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

def get_chat_administrators(chat_id, bot_token):
    url = f"https://api.telegram.org/bot{bot_token}/getChatAdministrators"
    params = {"chat_id": chat_id}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()['result']
    else:
        logger.error(f"Failed to get chat administrators: {response.text}")
        return None

@api_blueprint.route("/api/init", methods=['POST', 'OPTIONS'])
@token_required(fail_if_not_ready=False)
def validate_telegram_init_data():
    """
    Validate the InitData received from Telegram mini app.
    """
    community = request.community
    user_info = request.user_info
    is_admin = request.is_admin

    return jsonify({
        "valid": True,
        "ready": community['status'] == 'READY',
        "admin": is_admin,
        "community": community,
        "user": {
            "first_name": user_info['first_name'],
            "last_name": user_info['last_name'],
            "username": user_info['username']
        }
    })

@api_blueprint.route("/api/theming", methods=['POST', 'OPTIONS'])
def handle_theming():
    """
    Handle theming parameters received from Telegram mini app.
    """
    logger.info(f"Received theme parameters: {request.json}")
    return jsonify({"message": "Theme parameters received successfully"}), 200


@api_blueprint.route("/api/community/_setup", methods=['POST', 'OPTIONS'])
@token_required(fail_if_not_ready=False)
def setup_community():
    """
    Setup a community.
    """
    logger.info(f"Received setup parameters: {request.json}")

    if not request.is_admin:
        return jsonify({"error": "You don't have permission to setup the community"}), 403

    if request.community['status'] == 'READY':
        return jsonify({"error": "Community is already setup"}), 400

    setup_data = request.json
    
    if not setup_data.get('language') or not setup_data.get('location') or not setup_data.get('entitySettings'):
        return jsonify({"error": "Missing required parameters"}), 400

    service_manager.update_community(request.community['id'], {
        "status": "READY",
        "language": setup_data.get('language'),
        "location": setup_data.get('location'),
        "entitySettings": setup_data.get('entitySettings')
    })
    return jsonify({"message": "Setup parameters received successfully"}), 200



@api_blueprint.route("/api/items", methods=['GET', 'OPTIONS'])
@token_required()
def search_items():
    """
    Search for items.
    """

    try:
        items = service_manager.search_items(request.community['id'])
        return jsonify({"items": items})
    except Exception as e:
        logger.error(f"Error searching items: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_blueprint.route("/api/services", methods=['GET', 'OPTIONS'])
@token_required()
def search_services():
    """
    Search for services.
    """

    try:
        services = service_manager.search_services(request.community['id'])
        return jsonify({"services": services})
    except Exception as e:
        logger.error(f"Error searching services: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_blueprint.route("/api/events", methods=['GET', 'OPTIONS'])
@token_required()
def search_events():
    """
    Search for events.
    """

    try:
        events = service_manager.search_events(request.community['id'])
        return jsonify({"events": events})
    except Exception as e:
        logger.error(f"Error searching events: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_blueprint.route("/api/news", methods=['GET', 'OPTIONS'])
@token_required()
def search_news():
    """
    Search for news.
    """

    try:
        news = service_manager.search_news(request.community['id'])
        return jsonify({"news": news})
    except Exception as e:
        logger.error(f"Error searching news: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_blueprint.route("/api/items/<item_id>", methods=['DELETE', 'OPTIONS'])
@token_required()
def delete_item(item_id):
    """
    Delete an item by its ID and its associated image if it exists.
    """
    community_id = request.community['id']
    user_info = request.user_info
    is_admin = request.is_admin

    try:
        deleted_item = service_manager.delete_item(item_id, community_id, user_info['username'], is_admin)
        if deleted_item:
            image_deleted = delete_image_if_exists(deleted_item)
            return jsonify({"message": "Item deleted successfully", "image_deleted": image_deleted}), 200
        else:
            return jsonify({"error": "Item not found or you don't have permission to delete it"}), 404
    except Exception as e:
        logger.error(f"Error deleting item: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_blueprint.route("/api/services/<service_id>", methods=['DELETE', 'OPTIONS'])
@token_required()
def delete_service(service_id):
    """
    Delete a service by its ID and its associated image if it exists.
    """
    community_id = request.community['id']
    user_info = request.user_info
    is_admin = request.is_admin

    try:
        deleted_service = service_manager.delete_service(service_id, community_id, user_info['username'], is_admin)
        if deleted_service:
            image_deleted = delete_image_if_exists(deleted_service)
            return jsonify({"message": "Service deleted successfully", "image_deleted": image_deleted}), 200
        else:
            return jsonify({"error": "Service not found or you don't have permission to delete it"}), 404
    except Exception as e:
        logger.error(f"Error deleting service: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_blueprint.route("/api/events/<event_id>", methods=['DELETE', 'OPTIONS'])
@token_required()
def delete_event(event_id):
    """
    Delete an event by its ID and its associated image if it exists.
    """
    community_id = request.community['id']
    user_info = request.user_info
    is_admin = request.is_admin

    try:
        deleted_event = service_manager.delete_event(event_id, community_id, user_info['username'], is_admin)
        if deleted_event:
            image_deleted = delete_image_if_exists(deleted_event)
            return jsonify({"message": "Event deleted successfully", "image_deleted": image_deleted}), 200
        else:
            return jsonify({"error": "Event not found or you don't have permission to delete it"}), 404
    except Exception as e:
        logger.error(f"Error deleting event: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_blueprint.route("/api/news/<news_id>", methods=['DELETE', 'OPTIONS'])
@token_required()
def delete_news(news_id):
    """
    Delete a news item by its ID and its associated image if it exists.
    """
    community_id = request.community['id']
    user_info = request.user_info
    is_admin = request.is_admin

    try:
        deleted_news = service_manager.delete_news(news_id, community_id, user_info['username'], is_admin)
        if deleted_news:
            image_deleted = delete_image_if_exists(deleted_news)
            return jsonify({"message": "News item deleted successfully", "image_deleted": image_deleted}), 200
        else:
            return jsonify({"error": "News item not found or you don't have permission to delete it"}), 404
    except Exception as e:
        logger.error(f"Error deleting news item: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_blueprint.route("/api/items/<item_id>", methods=['PUT', 'OPTIONS'])
@token_required()
def update_item(item_id):
    """
    Update an item by its ID.
    """
    community_id = request.community['id']
    user_info = request.user_info
    is_admin = request.is_admin
    new_title = request.json.get('title')
    new_description = request.json.get('description')
    new_price = request.json.get('price')
    new_currency = request.json.get('currency')
    new_category = request.json.get('category')

    try:
        updated_item = service_manager.update_item(item_id, community_id, user_info['username'], is_admin, new_title, new_description, new_price, new_currency, new_category)
        return jsonify({"message": "Item updated successfully", "item": updated_item}), 200
    except Exception as e:
        logger.error(f"Error updating item: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_blueprint.route("/api/services/<service_id>", methods=['PUT', 'OPTIONS'])
@token_required()
def update_service(service_id):
    """
    Update a service by its ID.
    """
    community_id = request.community['id']
    user_info = request.user_info
    is_admin = request.is_admin

    new_title = request.json.get('title')
    new_description = request.json.get('description')
    new_price = request.json.get('price')
    new_currency = request.json.get('currency')
    new_category = request.json.get('category')

    try:
        updated_service = service_manager.update_service(service_id, community_id, user_info['username'], new_title, new_description, new_price, new_currency, new_category)
        return jsonify({"message": "Service updated successfully", "service": updated_service}), 200
    except Exception as e:
        logger.error(f"Error updating service: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_blueprint.route("/api/events/<event_id>", methods=['PUT', 'OPTIONS'])
@token_required()
def update_event(event_id):
    """
    Update an event by its ID.
    """
    community_id = request.community['id']
    user_info = request.user_info

    new_title = request.json.get('title')
    new_description = request.json.get('description')
    new_date = request.json.get('date')
    new_category = request.json.get('category')

    try:
        updated_event = service_manager.update_event(event_id, community_id, user_info['username'], new_title, new_description, new_date, new_category)
        return jsonify({"message": "Event updated successfully", "event": updated_event}), 200
    except Exception as e:
        logger.error(f"Error updating event: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_blueprint.route("/api/news/<news_id>", methods=['PUT', 'OPTIONS'])
@token_required()
def update_news(news_id):
    """
    Update a news item by its ID.
    """
    community_id = request.community['id']
    user_info = request.user_info

    new_title = request.json.get('title')
    new_description = request.json.get('description')
    new_category = request.json.get('category')

    try:
        updated_news = service_manager.update_news(news_id, community_id, user_info['username'], new_title, new_description, new_category)
        return jsonify({"message": "News item updated successfully", "news": updated_news}), 200
    except Exception as e:
        logger.error(f"Error updating news item: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500
