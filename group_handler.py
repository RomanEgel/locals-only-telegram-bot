import logging
import time
from itertools import islice
from common_utils import (
    send_message, send_app_keyboard,
    process_image_or_document, handle_entity_creation_from_hashtag,
    send_entity_link, get_supported_language
)
from config import service_manager

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
    elif 'media_group_id' in message:
        handle_media_group(message)

def handle_media_group(message):
    """
    Handle a media group message.
    """
    chat_id = message['chat']['id']
    
    # Check if the community exists, if not, create it and start setup
    community = service_manager.get_community_by_chat_id(chat_id)
    if not community:
        return
    
    media_group_id = message['media_group_id']
    if not service_manager.get_media_group(media_group_id):
        return
    
    image_url = process_image_or_document(message, community['id'])
    service_manager.add_image_to_media_group(media_group_id, image_url)
    logger.info(f"Added image to media group: {media_group_id}")

def handle_command(message, command):
    """
    Handle bot commands.
    """
    chat_id = message['chat']['id']
    
    # Check if the community exists, if not, create it and start setup
    community = service_manager.get_community_by_chat_id(chat_id)
    if not community:
        # Get the user's language code from the message
        user_language_code = get_supported_language(message['from'].get('language_code', 'en'))
        
        community = service_manager.create_community(chat_id, message['chat']['title'], user_language_code)
        logger.info(f"Created new community for chat_id: {chat_id} with initial language: {user_language_code}")

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

    if message['from']['username'] == 'GroupAnonymousBot':
        logger.info(f"Message from anonymous admin, skipping.")
        return

    community = service_manager.get_community_by_chat_id(chat_id)
    if not community:
        logger.info(f"Community not found for chat_id: {chat_id}")
        return

    entity, image_url = handle_entity_creation_from_hashtag(message, community, is_caption, is_private=False)
    if entity and entity['messageId']:
        users = service_manager.search_users_in_community(community['id'], {"notificationsEnabled": True, "chatId": {"$ne": "null"}})
        
        # Process users in batches of 30
        batch_size = 30
        user_list = list(users)
        
        for i in range(0, len(user_list), batch_size):
            # Get the next batch of users
            batch = list(islice(user_list, i, i + batch_size))
            
            # Forward messages to users in the current batch
            for user in batch:
                send_entity_link(user['chatId'], community['id'], entity['id'], entity['title'], community.get('language', 'en'), image_url)
            
            # If there are more messages to send, wait 1 second before the next batch
            if i + batch_size < len(user_list):
                time.sleep(1)
