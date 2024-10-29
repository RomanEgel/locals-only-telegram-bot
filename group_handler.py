import logging
from common_utils import (
    WEB_APP_LINK, send_message, send_app_keyboard, get_entity_class,
    process_image_or_document, set_message_reaction, extract_entity_type_from_hashtag
)
from config import service_manager
from ai_extractor import extract_entity_info_with_ai

logger = logging.getLogger(__name__)

def handle_group_message(message):
    """
    Handle incoming messages from group chats.
    """
    if message['from']['is_bot'] and message['from']['username'] != 'GroupAnonymousBot':
        return  # Ignore messages from bots except anonymous admins

    chat_id = message['chat']['id']
    text = message.get('text', '')

    logger.info(f"Received group message: {text} from chat_id: {chat_id}")

    if text.startswith('/'):
        handle_command(message, text)
    elif '#' in text:
        handle_hashtag(message)
    elif ('photo' in message or 'document' in message) and 'caption' in message and '#' in message['caption']:
        if 'document' in message:
            mime_type = message['document'].get('mime_type', '')
            if not mime_type.startswith('image/'):
                return  # Ignore non-image documents
        handle_hashtag(message, is_caption=True)

def handle_command(message, command):
    """
    Handle bot commands.
    """
    chat_id = message['chat']['id']
    
    # Check if the community exists, if not, create it and start setup
    community = service_manager.get_community_by_chat_id(chat_id)
    if not community:
        # Get the user's language code from the message
        user_language_code = message['from'].get('language_code', 'en')
        # Map the language code to 'en' or 'ru', defaulting to 'en' for unsupported languages
        initial_language = 'ru' if user_language_code.startswith('ru') else 'en'
        
        community = service_manager.create_community(chat_id, message['chat']['title'], initial_language)
        logger.info(f"Created new community for chat_id: {chat_id} with initial language: {initial_language}")

    # Check if the user is already in the community
    if message['from'].get('username') != 'GroupAnonymousBot':
        service_manager.add_user_to_community_if_not_exists(message['from']['id'], community['id'])

    # Extract the command without the bot name if it includes '@'
    command = command.split('@')[0]
    logger.info(f"Handling command: {command} for chat_id: {chat_id}")

    language = community.get('language', 'en')

    if command == '/start':
        send_message(chat_id, 'welcome', language)
    elif command == '/help':
        send_message(chat_id, 'help', language)
    elif command == '/app':
        send_app_keyboard(chat_id, community)

def handle_hashtag(message, is_caption=False):
    """
    Handle a message with a hashtag.
    """
    chat_id = message['chat']['id']
    message_id = message['message_id']
    text = message['caption'] if is_caption else message['text']
    user_id = message['from']['id']  # Get user ID

    if message['from']['username'] == 'GroupAnonymousBot':
        logger.info(f"Message from anonymous admin, skipping.")
        return

    community = service_manager.get_community_by_chat_id(chat_id)
    if not community:
        logger.info(f"Community not found for chat_id: {chat_id}")
        return

    if community.get('status', 'SETUP') != "READY":
        logger.info(f"Community {community['id']} is not ready")
        return
    
    service_manager.add_user_to_community_if_not_exists(user_id, community['id'])

    entity_settings = community.get('entitySettings', {
        'eventHashtag': '#event',
        'itemHashtag': '#item',
        'serviceHashtag': '#service',
        'newsHashtag': '#news'
    })

    entity_type, hashtag = extract_entity_type_from_hashtag(text, entity_settings)
    if not entity_type:
        logger.info(f"No supported hashtag found in message: {text}")
        return

    language = community.get('language', 'en')
    
    entity_class = get_entity_class(entity_type)
    if not entity_class:
        logger.info(f"Unsupported entity type: {entity_type}")
        return

    text_without_hashtag = text.replace(f'#{hashtag}', '').strip()

    if entity_type == 'event':
        existing_categories = service_manager.get_event_categories_by_community_id(community['id'])
    elif entity_type == 'news':
        existing_categories = service_manager.get_news_categories_by_community_id(community['id'])
    elif entity_type == 'item':
        existing_categories = service_manager.get_item_categories_by_community_id(community['id'])
    elif entity_type == 'service':
        existing_categories = service_manager.get_service_categories_by_community_id(community['id'])

    extracted_info = extract_entity_info_with_ai(text_without_hashtag, existing_categories, community['name'], entity_class, language)
    
    if extracted_info is None:
        logger.info(f"Failed to extract {entity_type} information")
        return

    # Populate missing fields with information from the Telegram message
    structure = entity_class.get_structure()
    for key, (value_type, default_value, _, _, _) in structure.items():
        if key not in extracted_info:
            if key == 'author':
                extracted_info[key] = f"{message['from']['first_name']} {message['from'].get('last_name', '')}".strip()
            elif key == 'userId':
                extracted_info[key] = user_id
            elif key == 'images':
                image_url = process_image_or_document(message, community['id'])
                extracted_info[key] = [image_url] if image_url else default_value()
            elif key == 'communityId':
                extracted_info[key] = community['id']
            elif key == 'messageId':
                extracted_info[key] = message['message_id']
            elif key == 'mediaGroupId':
                extracted_info[key] = message.get('media_group_id') if message.get('media_group_id') else default_value()
            else:
                extracted_info[key] = default_value()

    # Process the extracted_info
    try:
        if entity_type == 'event':
            service_manager.create_event(**extracted_info)
        elif entity_type == 'news':
            service_manager.create_news(**extracted_info)
        elif entity_type == 'item':
            service_manager.create_item(**extracted_info)
        elif entity_type == 'service':
            service_manager.create_service(**extracted_info)
        
        logger.info(f"Processed {entity_type} for chat_id: {chat_id}")
        set_message_reaction(chat_id, message_id, "⚡")
    except Exception as e:
        logger.error(f"Error processing {entity_type}: {str(e)}", exc_info=True)