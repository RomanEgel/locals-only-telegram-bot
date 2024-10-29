import logging
from common_utils import send_app_keyboard, send_message, send_message_with_keyboard  # Updated import
from config import service_manager

logger = logging.getLogger(__name__)

def handle_private_message(message):
    """
    Handle incoming messages from private chats.
    """
    # Ignore messages from bots
    if message['from'].get('is_bot', False):
        logger.info("Ignoring message from bot")
        return

    chat_id = message['chat']['id']
    text = message.get('text', '')
    user_id = message['from']['id']

    logger.info(f"Received private message: {text} from chat_id: {chat_id}")

    # Get or create LocalsUser
    user = service_manager.get_user(user_id)
    if not user:
        user = service_manager.create_user(user_id, [])
        logger.info(f"Created new user with id: {user_id}")
    else:
        logger.info(f"Found existing user with id: {user_id}")

    if text.startswith('/'):
        handle_private_command(message, text, user)
    elif 'chat_shared' in message:
        handle_chat_shared(message, user)
    elif '#' in text:
        handle_private_hashtag(message, user)
    elif ('photo' in message or 'document' in message) and 'caption' in message and '#' in message['caption']:
        if 'document' in message:
            mime_type = message['document'].get('mime_type', '')
            if not mime_type.startswith('image/'):
                return  # Ignore non-image documents
        handle_private_hashtag(message, user, is_caption=True)

def handle_chat_shared(message, user):
    """
    Handle chat_shared message.
    """
    chat_shared = message['chat_shared']
    chat_id = message['chat']['id']
    community_chat_id = chat_shared['chat_id']

    request_id = chat_shared['request_id']

    if request_id != 1 and request_id != 2:
        logger.info(f"Unsupported request_id for chat shared message: {request_id}")
        return

    community = service_manager.get_community_by_chat_id(community_chat_id)    

    if request_id == 1:
        if not community:
            send_message_with_keyboard(chat_id, 'community_not_found', reply_markup={'remove_keyboard': True})
            return
        service_manager.add_user_to_community(user['id'], community['id'])
        send_message_with_keyboard(chat_id, 'successfully_joined', reply_markup={'remove_keyboard': True})
        send_app_keyboard(chat_id, community)
    elif request_id == 2:
        if community:
            send_message_with_keyboard(chat_id, 'community_already_exists', reply_markup={'remove_keyboard': True})
            send_app_keyboard(chat_id, community)
            return
        else:
            chat_title = chat_shared['title']
            community = service_manager.create_community(community_chat_id, chat_title, message['from'].get('language_code', 'en'))
            service_manager.add_user_to_community(user['id'], community['id'])
            send_message_with_keyboard(chat_id, 'community_created', reply_markup={'remove_keyboard': True})
            send_app_keyboard(chat_id, community)

def handle_private_hashtag(message, user, is_caption=False):
    """
    Handle hashtags in private chats.
    """
    chat_id = message['chat']['id']
    text = message.get('text', '')
    user_id = message['from']['id']
    

    logger.info(f"Received private message: {text} from chat_id: {chat_id}")

def handle_private_command(message, command, user):
    """
    Handle bot commands in private chats.
    """
    chat_id = message['chat']['id']
    
    # Extract the command without the bot name if it includes '@'
    command = command.split('@')[0]

    logger.info(f"Handling private command: {command} for chat_id: {chat_id}")

    if command == '/start':
        send_message(chat_id, 'private_welcome')
    elif command == '/help':
        send_message(chat_id, 'private_help')
    elif command == '/join':
        button = {
            'text': "Select a community chat to join",
            'request_chat': {
                'request_id': 1,
                'chat_is_channel': False
            }
        }
        send_message_with_keyboard(chat_id, 'please_select_chat', reply_markup={'keyboard': [[button]], 'resize_keyboard': True, 'one_time_keyboard': True})    
    elif command == '/create':
        button = {
            'text': "Select a new community chat",
            'request_chat': {
                'request_id': 2,
                'chat_is_channel': False,
                'user_administrator_rights': {
                    'can_promote_members': True,
                },
                'bot_administrator_rights': {
                  'can_manage_chat': True,
                },
                'request_title': True,
            }
        }
        send_message_with_keyboard(chat_id, 'please_select_chat', reply_markup={'keyboard': [[button]], 'resize_keyboard': True, 'one_time_keyboard': True})

    # Add more private chat commands as needed