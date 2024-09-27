from flask import Blueprint, request, jsonify
import os
import logging
import requests
import re
from config import service_manager, storage_client  # Import storage_client
from ai_extractor import extract_entity_info_with_ai
from service import BaseEntity, LocalsItem, LocalsService, LocalsEvent, LocalsNews  # Import entity classes
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the Blueprint
bot_blueprint = Blueprint('bot', __name__)

# Telegram Bot Token
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Web App Link
WEB_APP_LINK = "https://t.me/locals_only_bot/localsOnly"

# Google Cloud Storage bucket name
GCS_BUCKET_NAME = "locals-only-community-data"

def send_message(chat_id, text_key, language='en', **kwargs):
    translations = {
        'en': {
            'welcome': "Welcome to the bot!",
            'help': "Here are the available commands: /start, /help, /app",
        },
        'ru': {
            'welcome': "Добро пожаловать в бота!",
            'help': "Вот доступные команды: /start, /help, /app",
        }
    }

    text = translations[language][text_key].format(**kwargs)

    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text
    }
    response = requests.post(url, json=payload)
    return response.json()

@bot_blueprint.route("/bot", methods=['POST'])
def handle_telegram_event():
    """
    Handle incoming Telegram events.
    """
    try:
        event = request.get_json()
        logger.info(f"Received event: {event}")

        if 'message' in event:
            handle_message(event['message'])
    except Exception as e:
        logger.error(f"Error handling Telegram event: {str(e)}", exc_info=True)
    
    return jsonify({"status": "ok"}), 200

def handle_message(message):
    """
    Handle incoming messages.
    """
    if message['from']['is_bot'] and message['from']['username'] != 'GroupAnonymousBot':
        return  # Ignore messages from bots except anonymous admins

    chat_id = message['chat']['id']
    chat_type = message['chat']['type']
    text = message.get('text', '')

    logger.info(f"Received message: {text} from chat_id: {chat_id}")

    # Check if the message is from a group chat
    if chat_type != 'group' and chat_type != 'supergroup':
        logger.info(f"Message is not from a group chat, skipping.")
        return

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


def handle_hashtag(message, is_caption=False):
    """
    Handle a message with a hashtag.
    """
    chat_id = message['chat']['id']
    message_id = message['message_id']
    text = message['caption'] if is_caption else message['text']
    username = message['from']['username']  # Get username

    if message['from']['username'] == 'GroupAnonymousBot':
        logger.info(f"Message from anonymous admin, skipping.")
        return
    
    hashtag = extract_valid_hashtag(text)
    if not hashtag:
        logger.info(f"No supported hashtag found in message: {text}")
        return

    community = service_manager.get_community_by_chat_id(chat_id)
    if not community:
        logger.info(f"Community not found for chat_id: {chat_id}")
        return
    if community.get('status', 'SETUP') != "READY":
        logger.info(f"Community {community['id']} is not ready")
        return

    language = community.get('language', 'en')
    
    entity_type = hashtag  # Assuming hashtag corresponds to entity_type
    entity_class = get_entity_class(entity_type)
    if not entity_class:
        logger.info(f"Unsupported entity type: {entity_type}")
        return

    text_without_hashtag = text.replace(f'#{hashtag}', '').strip()
    extracted_info = extract_entity_info_with_ai(text_without_hashtag, entity_class, language)
    
    if extracted_info is None:
        logger.info(f"Failed to extract {entity_type} information")
        return

    # Populate missing fields with information from the Telegram message
    structure = entity_class.get_structure()
    for key, (value_type, default_value, _, _, _) in structure.items():
        if key not in extracted_info:
            if key == 'author':
                extracted_info[key] = f"{message['from']['first_name']} {message['from'].get('last_name', '')}".strip()
            elif key == 'username':
                extracted_info[key] = username  # Set username
            elif key == 'image':
                image_url = process_image_or_document(message, community['id'])
                extracted_info[key] = image_url if image_url else default_value()
            elif key == 'communityId':
                extracted_info[key] = community['id']
            elif key == 'messageId':
                extracted_info[key] = message['message_id']  # Set messageId
            else:
                extracted_info[key] = default_value()

    # Process the extracted_info
    try:
        if hashtag == 'event':
            service_manager.create_event(**extracted_info)
        elif hashtag == 'news':
            service_manager.create_news(**extracted_info)
        elif hashtag == 'item':
            service_manager.create_item(**extracted_info)
        elif hashtag == 'service':
            service_manager.create_service(**extracted_info)
        
        logger.info(f"Processed {hashtag} for chat_id: {chat_id}")
        set_message_reaction(chat_id, message_id, "⚡")
    except Exception as e:
        logger.error(f"Error processing {hashtag}: {str(e)}", exc_info=True)

def set_message_reaction(chat_id, message_id, emoji):
    """
    Set a reaction emoji on a message.
    """
    url = f"{TELEGRAM_API_URL}/setMessageReaction"
    payload = {
        'chat_id': chat_id,
        'message_id': message_id,
        'reaction': [{'type': 'emoji', 'emoji': emoji}]
    }
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        logger.error(f"Failed to set reaction: {response.text}")

def extract_valid_hashtag(text):
    """
    Extract the first valid hashtag from the message.
    """
    valid_hashtags = ['event', 'news', 'item', 'service']
    hashtags = re.findall(r'#(\w+)', text.lower())
    for hashtag in hashtags:
        if hashtag in valid_hashtags:
            return hashtag
    return None

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

    # Extract the command without the bot name if it includes '@'
    command = command.split('@')[0]

    logger.info(f"Handling command: {command} for chat_id: {chat_id}")

    language = community.get('language', 'en')

    if command == '/start':
        send_message(chat_id, 'welcome', language)
    elif command == '/help':
        send_message(chat_id, 'help', language)
    elif command == '/app':
        send_inline_keyboard(chat_id, 'community_app', WEB_APP_LINK + f"?startapp={community['id']}", language)

def send_inline_keyboard(chat_id, text_key, url, language='en'):
    translations = {
        'en': {
            'community_app': "Community App",
            'open_web_app': "Open"
        },
        'ru': {
            'community_app': "Приложение Сообщества",
            'open_web_app': "Открыть"
        }
    }

    text = translations[language][text_key]
    button_text = translations[language]['open_web_app']

    api_url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'reply_markup': {
            'inline_keyboard': [[
                {
                    'text': button_text,
                    'url': url
                }
            ]]
        }
    }
    response = requests.post(api_url, json=payload)
    return response.json()

def get_entity_class(entity_type):
    """
    Get the entity class based on the entity type.
    """
    entity_classes = {
        'event': LocalsEvent,
        'news': LocalsNews,
        'item': LocalsItem,
        'service': LocalsService
    }
    return entity_classes.get(entity_type)

def download_image(file_id):
    """
    Download image from Telegram servers.
    """
    file_path_url = f"{TELEGRAM_API_URL}/getFile?file_id={file_id}"
    file_path_response = requests.get(file_path_url)
    file_path = file_path_response.json()['result']['file_path']
    
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    file_response = requests.get(file_url)
    
    return file_response.content

def upload_to_gcs(file_content, destination_blob_name):
    """
    Upload file to Google Cloud Storage.
    """
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_string(file_content)
    
    return blob.public_url

def process_image(file_id, community_id):
    """
    Download image from Telegram and upload to GCS.
    """
    try:
        file_content = download_image(file_id)
        file_url = upload_to_gcs(file_content, f"{community_id}/{file_id}.jpg")
        return file_url
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}", exc_info=True)
        return None

def process_image_or_document(message, community_id):
    """
    Process image from photo or document in the message.
    """
    if 'photo' in message:
        return process_image(message['photo'][-1]['file_id'], community_id)
    elif 'document' in message:
        mime_type = message['document'].get('mime_type', '')
        if mime_type.startswith('image/'):
            return process_image(message['document']['file_id'], community_id)
    logger.info(f"No valid image found in message for community id: {community_id}")
    return None  # Return None if no valid image is found
