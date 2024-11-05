import logging
from common_utils import send_app_keyboard, send_message, send_message_with_keyboard, send_app_list_keyboard, send_advertise_setup_keyboard, get_chat_administrators, get_supported_language  # Updated import
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
        user = service_manager.create_user(user_id, [], chat_id)
        logger.info(f"Created new user with id: {user_id}")
    else:
        logger.info(f"Found existing user with id: {user_id}")
        if not user.get('chatId', None):
            service_manager.set_user_chat_id(user_id, chat_id)
            logger.info(f"Updated chat_id for user with id: {user_id}")

    if text.startswith('/'):
        handle_private_command(message, text, user)
    elif 'chat_shared' in message:
        handle_chat_shared(message, user)

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
        admins = get_chat_administrators(community_chat_id)
        if admins is None:
            send_message_with_keyboard(chat_id, 'bot_has_no_administrator_rights', reply_markup={'remove_keyboard': True})
            return

        if community:
            send_message_with_keyboard(chat_id, 'community_already_exists', reply_markup={'remove_keyboard': True})
            send_app_keyboard(chat_id, community)
            return
        else:
            chat_title = chat_shared['title']
            community = service_manager.create_community(community_chat_id, chat_title, get_supported_language(message['from'].get('language_code', 'en')))
            service_manager.add_user_to_community(user['id'], community['id'])
            send_message_with_keyboard(chat_id, 'community_created', reply_markup={'remove_keyboard': True})
            send_app_keyboard(chat_id, community)    


def handle_private_command(message, command, user):
    """
    Handle bot commands in private chats.
    """
    chat_id = message['chat']['id']
    user_language = get_supported_language(message['from'].get('language_code', 'en'))
    
    # Extract the command without the bot name if it includes '@'
    command = command.split('@')[0]

    logger.info(f"Handling private command: {command} for chat_id: {chat_id}")

    if command == '/start':
        send_message(chat_id, 'private_welcome')
    elif command == '/help':
        send_message(chat_id, 'private_help')
    elif command == '/enable_notifications':
        service_manager.set_user_notifications_enabled(user['id'], True)
        send_message(chat_id, 'notifications_enabled')
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
    elif command == '/list':
        communities = [service_manager.get_community_by_id(community_id) for community_id in user['communities']]
        if not communities:
            send_message(chat_id, 'no_communities', language=user_language)
            return

        send_app_list_keyboard(chat_id, communities, user_language)
    elif command == '/advertise':
        send_advertise_setup_keyboard(chat_id, user_language)

    # Add more private chat commands as needed