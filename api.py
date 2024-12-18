import random
import uuid
from flask import Blueprint, request, jsonify
import os
import hashlib
import hmac
from urllib.parse import parse_qsl
import logging
from functools import wraps
from config import service_manager, storage_client  # Import storage_client from config
from common_utils import get_chat, get_chat_administrators, get_chat_member
import json
import requests
from common_utils import get_supported_language, is_language_supported, is_currency_supported, is_location_in_range, generate_gcs_upload_link_for_image, check_file_exists_in_gcs, send_ad_link
import threading
import time

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

def token_required(community_specific_request=True):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            community_id_header = request.headers.get('X-Community-Id')
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
                
                # Extract user information from parsed_data
                user_info_str = parsed_data.get('user', '{}')
                try:
                    user_info = json.loads(user_info_str)
                    request.user_info = user_info  # Store user info in request context
                except json.JSONDecodeError:
                    logger.error(f"Error decoding user info: {user_info_str}")
                    return jsonify({"error": "Invalid user information"}), 400

                start_param = parsed_data.get('start_param', '')
                if start_param == 'advertise':
                    if community_specific_request:
                        return jsonify({"error": "Invalid request"}), 400
                    else:
                        request.advertise = True
                        return f(*args, **kwargs)
                
                if start_param:
                    split = start_param.split('_')
                    community_id = split[0]
                    entity_id = split[1] if len(split) > 1 else None
                else:
                    community_id = None
                    entity_id = None

                if not community_id:
                    if community_id_header:
                        user = service_manager.get_user(user_info['id'])
                        if user and community_id_header not in user['communities']:
                            return jsonify({"error": "User is not part of this community"}), 404
                        community_id = community_id_header
                    elif community_specific_request:
                        return jsonify({"error": "Invalid request"}), 400
                    else:
                        request.community_is_not_specified = True
                        return f(*args, **kwargs)
                
                community = service_manager.get_community_by_id(community_id)
                if entity_id:
                    entity, entity_type = service_manager.get_entity_by_id(entity_id)
                    request.entity = entity
                    request.entity_type = entity_type
                if not community:
                    return jsonify({"valid": False}), 404
                
                if community_specific_request and community['status'] != 'READY':
                    return jsonify({"error": "Community is not ready"}), 403

                # Get chat administrators
                admins = get_chat_administrators(community['chatId'])
                
                if admins is None:
                    return jsonify({"error": "Failed to get chat administrators"}), 500

                request.parsed_data = parsed_data  # Store parsed data in request context
                request.community = community  # Store community in request context

                admin_usernames = [admin['user']['username'] for admin in admins if 'username' in admin['user']]
                
                request.is_admin = user_info['username'] in admin_usernames  # Store admin status in request context
                return f(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error validating init data: {str(e)}", exc_info=True)
                return jsonify({"error": str(e)}), 400

        return decorated_function
    return decorator

@api_blueprint.route("/api/init", methods=['POST', 'OPTIONS'])
@token_required(community_specific_request=False)
def validate_telegram_init_data():
    """
    Validate the InitData received from Telegram mini app.
    """
    user_info = request.user_info
    user = service_manager.get_user(user_info['id'])
    if not user:
        user = service_manager.create_user(user_info['id'], [])

    if getattr(request, 'advertise', False):        
        return jsonify({
            "valid": True, 
            "advertise": True, 
            "user": {
                "id": user_info['id'],
                "first_name": user_info['first_name'],
                "last_name": user_info['last_name'],
                "username": user_info['username'],
                "language_code": get_supported_language(user_info.get('language_code', 'en'))
            }})

    if getattr(request, 'community_is_not_specified', False):
        community_ids = user.get('communities', [])
        return jsonify({
                "valid": True,
                "community_is_not_specified": True,
                "communities": [service_manager.get_community_by_id(id) for id in community_ids],
                "user": {
                    "id": user_info['id'],
                    "first_name": user_info['first_name'],
                    "last_name": user_info['last_name'],
                    "username": user_info['username'],
                    "notifications_enabled": user.get('notificationsEnabled', False)
                }
            })
    
    community = request.community
    is_admin = request.is_admin
    
    if community['id'] not in user['communities']:
        service_manager.add_user_to_community(user['id'], community['id'])

    return jsonify({
        "valid": True,
        "ready": community['status'] == 'READY',
        "admin": is_admin,
        "community": community,
        "entity": getattr(request, 'entity', None),
        "entity_type": getattr(request, 'entity_type', None),
        "user": {
            "id": user_info['id'],
            "first_name": user_info['first_name'],
            "last_name": user_info['last_name'],
            "username": user_info['username'],
            "notifications_enabled": user.get('notificationsEnabled', False)
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
@token_required(community_specific_request=False)
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
    
    if not is_language_supported(setup_data.get('language')):
        return jsonify({"error": "Unsupported language"}), 400
    
    if not setup_data.get('location').get('lat') or not setup_data.get('location').get('lng'):
        return jsonify({"error": "Missing location coordinates"}), 400

    service_manager.update_community(request.community['id'], {
        "status": "READY",
        "language": setup_data.get('language'),
        "location": setup_data.get('location'),
        "entitySettings": setup_data.get('entitySettings')
    })
    return jsonify({"message": "Setup parameters received successfully"}), 200


@api_blueprint.route("/api/communities/coordinates", methods=['GET', 'OPTIONS'])
@token_required(community_specific_request=False)
def get_communities_coordinates():
    """
    Get all communities coordinates.
    """
    if not getattr(request, 'advertise', False):
        return jsonify({"error": "Invalid request"}), 400
    
    communities = service_manager.get_all_communities()
    coordinates = [community.get('location', {}) for community in communities]
    return jsonify({"coordinates": coordinates}), 200

@api_blueprint.route("/api/media-groups", methods=['POST', 'OPTIONS'])
@token_required(community_specific_request=False)
def create_media_group_for_ad_image_upload():
    """
    Create a media group for an advertisement image upload.
    """
    logger.info(f"Received media group creation request: {request.json}")
    images_data = request.json['images']
    if not images_data or not isinstance(images_data, list) or len(images_data) < 1 or len(images_data) > 5:
        return jsonify({"error": "Missing images or invalid number of images"}), 400
    
    images = []
    upload_links = []
    for image_data in images_data:
        if not image_data.get('name') or not image_data.get('contentType'):
            return jsonify({"error": "Missing image name or content type"}), 400
        if not image_data['contentType'].startswith('image/'):
            return jsonify({"error": "Invalid image content type"}), 400
        gcs_public_url, gcs_upload_link = generate_gcs_upload_link_for_image(image_data['name'], image_data['contentType'])
        images.append(gcs_public_url)
        upload_links.append(gcs_upload_link)

    media_group = service_manager.create_media_group(str(uuid.uuid4()), images)
    return jsonify({"mediaGroupId": media_group["id"], "uploadLinks": upload_links}), 200
    

def send_user_created_ad(advertisement_id, image_preview_url, chat_id, language_code):
    """
    Function to be executed in a separate thread to send a message to the user about the created advertisement
    """
    
    try:
        logger.info(f"Processing advertisement notification for ad ID: {advertisement_id}")

        send_ad_link(chat_id, image_preview_url, language_code)
        
    except Exception as e:
        logger.error(f"Error processing advertisement notifications: {str(e)}", exc_info=True)

@api_blueprint.route("/api/advertisements", methods=['POST', 'OPTIONS'])
@token_required(community_specific_request=False)
def create_advertisement():
    """
    Create an advertisement.
    """
    logger.info(f"Received advertisement parameters: {request.json}")
    user_id = request.user_info['id']
    user = service_manager.get_user(user_id)
    if not user or not user['chatId']:
        return jsonify({"error": "User not found or user hasn't interacted with the bot yet"}), 404


    location = request.json.get('location')
    range = request.json.get('range')
    entity_type = request.json.get('entityType')
    title = request.json.get('title')
    description = request.json.get('description')
    price = request.json.get('price')
    currency = request.json.get('currency')
    media_group_id = request.json.get('mediaGroupId')

    if not title or not description or not price or not currency or not entity_type or not location or not range or not media_group_id:
        return jsonify({"error": "Missing required parameters"}), 400
    if entity_type not in ['item', 'service']:
        return jsonify({"error": "Invalid entity type"}), 400
    if not is_currency_supported(currency):
        return jsonify({"error": "Unsupported currency"}), 400
    if price <= 0 or price > 1000000:
        return jsonify({"error": "Invalid price"}), 400
    if not location.get('lat') or not location.get('lng'):
        return jsonify({"error": "Missing location coordinates"}), 400
    if range < 1 or range > 100:
        return jsonify({"error": "Invalid range"}), 400

    coordinates = [community.get('location', {}) for community in service_manager.get_all_communities()]
    if not is_location_in_range(location, coordinates, range):
        return jsonify({"error": "Location is out of range"}), 400
    
    media_groups = service_manager.get_media_groups([media_group_id])
    if not media_groups:
        return jsonify({"error": "Media group not found"}), 404
    media_group = media_groups[0]
    images = media_group['images']
    for gcs_public_url in images:
        if not check_file_exists_in_gcs(gcs_public_url):
            return jsonify({"error": "Images are not uploaded correctly"}), 404

    # Create the advertisement
    advertisement = service_manager.create_advertisement(
        user_id, 
        media_group_id, 
        location, 
        range, 
        entity_type, 
        title, 
        description, 
        price, 
        currency
    )

    # Start a new thread to process notifications
    notification_thread = threading.Thread(
        target=send_user_created_ad,
        args=(advertisement['id'], images[0], user['chatId'], get_supported_language(request.user_info.get('language_code', 'en')))
    )
    notification_thread.start()

    return jsonify({"message": "Advertisement created successfully", "id": advertisement['id']}), 200

@api_blueprint.route("/api/advertisements", methods=['GET', 'OPTIONS'])
@token_required(community_specific_request=False)
def get_user_advertisements():
    user_id = request.user_info['id']
    advertisements = service_manager.find_advertisements_by_user_id(user_id)
    populate_entities_with_images(advertisements)
    return jsonify({"advertisements": advertisements}), 200

@api_blueprint.route("/api/advertisements/<advertisement_id>", methods=['DELETE', 'OPTIONS'])
@token_required(community_specific_request=False)
def delete_advertisement(advertisement_id):
    user_id = request.user_info['id']
    deleted_advertisement = service_manager.delete_advertisement(advertisement_id, user_id)
    if deleted_advertisement:
        delete_images_if_exists(deleted_advertisement)
        return jsonify({"message": "Advertisement deleted successfully"}), 200
    else:
        return jsonify({"error": "Advertisement not found or you don't have permission to delete it"}), 404


@api_blueprint.route("/api/advertisements/_find-for-community", methods=['GET', 'OPTIONS'])
@token_required()
def get_advertisement_for_community():
    """
    Get the advertisement for a community.
    """
    community_id = request.community['id']
    community = service_manager.get_community_by_id(community_id)
    location = community['location']
    
    advertisements = service_manager.find_advertisements_for_location(location)
    ad = None
    if advertisements:
        # pick random ad
        ad = random.choice(advertisements)
        service_manager.increment_advertisement_views(ad['id'])
        populate_entities_with_images([ad])
    
    return jsonify({"advertisement": ad}), 200

@api_blueprint.route("/api/advertisements/<advertisement_id>/_resolve-user-link", methods=['GET', 'OPTIONS'])
@token_required()
def resolve_user_link_for_advertisement(advertisement_id):
    advertisement = service_manager.get_advertisement_by_id(advertisement_id)
    if advertisement:
        user = service_manager.get_user(advertisement['userId'])
        if not user:
            logger.info(f"User not found for advertisement {advertisement_id}, deleting advertisement")
            service_manager.delete_advertisement(advertisement_id, advertisement['userId'])
            return jsonify({"error": "User not found"}), 404
        chat_info = get_chat(user['chatId'])
        if chat_info:
            return jsonify({"link": f"https://t.me/{chat_info['username']}"}), 200
        else:
            logger.info(f"Chat not found for user {user['id']}, deleting advertisement {advertisement_id}")
            service_manager.delete_advertisement(advertisement_id, advertisement['userId'])
            return jsonify({"error": "Chat not found"}), 404
    else:
        return jsonify({"error": "Advertisement not found"}), 404
    
@api_blueprint.route("/api/users/<user_id>/_resolve-link", methods=['GET', 'OPTIONS'])
@token_required()
def resolve_user_link(user_id):
    """
    Resolve a user link.
    """
    chat_member = get_chat_member(request.community['chatId'], user_id)
    
    if chat_member:
        return jsonify({"link": f"https://t.me/{chat_member['user']['username']}"}), 200
    else:
        return jsonify({"error": "User not found"}), 404

@api_blueprint.route("/api/items", methods=['GET', 'OPTIONS'])
@token_required()
def search_items():
    """
    Search for items.
    """

    try:
        items = service_manager.search_items(request.community['id'])
        populate_entities_with_images(items)
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
        populate_entities_with_images(services)
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
        populate_entities_with_images(events)
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
        populate_entities_with_images(news)
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
        deleted_item = service_manager.delete_item(item_id, community_id, user_info['id'])
        if deleted_item:
            images_deleted = delete_images_if_exists(deleted_item)
            return jsonify({"message": "Item deleted successfully", "images_deleted": images_deleted}), 200
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
        deleted_service = service_manager.delete_service(service_id, community_id, user_info['id'])
        if deleted_service:
            images_deleted = delete_images_if_exists(deleted_service)
            return jsonify({"message": "Service deleted successfully", "images_deleted": images_deleted}), 200
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
        deleted_event = service_manager.delete_event(event_id, community_id, user_info['id'])
        if deleted_event:
            images_deleted = delete_images_if_exists(deleted_event)
            return jsonify({"message": "Event deleted successfully", "images_deleted": images_deleted}), 200
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
        deleted_news = service_manager.delete_news(news_id, community_id, user_info['id'])
        if deleted_news:
            images_deleted = delete_images_if_exists(deleted_news)
            return jsonify({"message": "News item deleted successfully", "images_deleted": images_deleted}), 200
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
        updated_item = service_manager.update_item(item_id, community_id, user_info['id'], new_title, new_description, new_price, new_currency, new_category)
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
        updated_service = service_manager.update_service(service_id, community_id, user_info['id'], new_title, new_description, new_price, new_currency, new_category)
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
        updated_event = service_manager.update_event(event_id, community_id, user_info['id'], new_title, new_description, new_date, new_category)
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
        updated_news = service_manager.update_news(news_id, community_id, user_info['id'], new_title, new_description, new_category)
        return jsonify({"message": "News item updated successfully", "news": updated_news}), 200
    except Exception as e:
        logger.error(f"Error updating news item: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

def delete_images_if_exists(entity):
    images_deleted = 0
    if entity and entity.get('mediaGroupId'):
        media_groups = service_manager.get_media_groups([entity['mediaGroupId']])
        if media_groups and media_groups[0].get('images'):
            media_group = media_groups[0]
            for image in media_group['images']:
                try:
                    image_gcs_path = image.replace('https://storage.googleapis.com/', '')
                    bucket_name, blob_name = image_gcs_path.split('/', 1)
                    bucket = storage_client.bucket(bucket_name)
                    blob = bucket.blob(blob_name)
                    blob.delete()
                    logger.info(f"Deleted image from GCS: {image_gcs_path}")
                    images_deleted += 1
                except Exception as e:
                    logger.error(f"Error deleting image from GCS: {str(e)}", exc_info=True)
            service_manager.delete_media_group(media_group['id'])
    return images_deleted

def populate_entities_with_images(entities):
    media_group_ids = [entity['mediaGroupId'] for entity in entities if entity['mediaGroupId']]
    media_groups = service_manager.get_media_groups(media_group_ids)
    media_groups_dict = {media_group['id']: media_group['images'] for media_group in media_groups}

    for entity in entities:
        entity['images'] = []
        if entity['mediaGroupId'] in media_groups_dict:
            entity['images'] = media_groups_dict[entity['mediaGroupId']]