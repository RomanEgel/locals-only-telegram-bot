import os
import logging
import requests
import re
from config import service_manager, storage_client
from service import BaseEntity, LocalsItem, LocalsService, LocalsEvent, LocalsNews

logger = logging.getLogger(__name__)

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
            'private_welcome': "Welcome to the private chat!",
            'private_help': "Here are the available commands for private chat: /start, /help",
            'private_chat_response': "This is a private chat. How can I assist you?",
        },
        'ru': {
            'welcome': "Добро пожаловать в бота!",
            'help': "Вот доступные команды: /start, /help, /app",
            'private_welcome': "Добро пожаловать в приватный чат!",
            'private_help': "Вот доступные команды для приватного чата: /start, /help",
            'private_chat_response': "Это приватный чат. Чем я могу вам помочь?",
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

def send_app_keyboard(chat_id, community):
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
    language = community.get('language', 'en')
    text_key = 'community_app'
    url = WEB_APP_LINK + f"?startapp={community['id']}"

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

def send_message_with_keyboard(chat_id, text_key, reply_markup=None, language='en'):
    """
    Send a message with keyboard buttons.
    """
    translations = {
        'en': {
            'please_select_chat': "Please select a chat:",
            'community_not_found': "Community not found for the shared chat. Please create a new one using the /create command.",
            'successfully_joined': "You have successfully joined the community!",
            'community_already_exists': "Community already exists for the shared chat.",
            'community_created': "Community created successfully!",
        },
        'ru': {
            'please_select_chat': "Пожалуйста, выберите чат:",
            'community_not_found': "Сообщество не найдено для указанного чата. Пожалуйста, создайте новое сообщество используя команду /create.",
            'successfully_joined': "Вы успешно присоединились к сообществу!",
            'community_already_exists': "Сообщество уже существует для указанного чата.",
            'community_created': "Сообщество успешно создано!",
        }
    }

    text = translations[language].get(text_key, text_key)  # Default to text_key if not found

    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'reply_markup': reply_markup
    }
    response = requests.post(url, json=payload)

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

def extract_entity_type_from_hashtag(text, entity_settings):
    """
    Extract the first valid hashtag from the message.
    """
    valid_hashtags = [entity_settings['eventHashtag'].lower(), entity_settings['newsHashtag'].lower(), entity_settings['itemHashtag'].lower(), entity_settings['serviceHashtag'].lower()]
    hashtags = re.findall(r'(#\w+)', text.lower())
    for hashtag in hashtags:
        if hashtag in valid_hashtags:
            for key, value in entity_settings.items():
                if value.lower() == hashtag:
                    return key.replace('Hashtag', ''), hashtag
    return None, None