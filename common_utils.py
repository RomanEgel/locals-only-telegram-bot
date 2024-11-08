import os
import logging
import uuid
import requests
import re
from config import service_manager, storage_client
from service import LocalsItem, LocalsService, LocalsEvent, LocalsNews
from ai_extractor import extract_entity_info_with_ai
from math import radians, sin, cos, sqrt, atan2
import google.auth

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
            'private_help': "Here are the available commands: /start, /help, /join, /create, /list",
            'private_chat_response': "This is a private chat. How can I assist you?",
            'notifications_enabled': "Notifications enabled!",
            'no_communities': "You are not a member of any communities.",
        },
        'ru': {
            'welcome': "Добро пожаловать в бота!",
            'help': "Вот доступные команды: /start, /help, /app",
            'private_welcome': "Добро пожаловать в приватный чат!",
            'private_help': "Вот доступные команды: /start, /help, /join, /create, /list",
            'private_chat_response': "Это приватный чат. Чем я могу вам помочь?",
            'no_communities': "Вы не являетесь участником ни одного сообщества.",
            'notifications_enabled': "Уведомления активированы!",
        }
    }

    text = translations[language][text_key].format(**kwargs)

    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'protect_content': True
    }
    response = requests.post(url, json=payload)
    return response.json()

def send_entity_link(chat_id, community_id, entity_id, entity_title, language, image_url):
    translations = {
        'en': {
            'open': "Open in App"
        },
        'ru': {
            'open': "Открыть в Приложении"
        }
    }
    
    url = WEB_APP_LINK + f"?startapp={community_id}_{entity_id}"
    keyboard = [
        [{'text': translations[language]['open'], 'url': url}]
    ]
    link_preview_options = {
        'prefer_large_media': True,
        'show_above_text': True,
        'url': image_url
    }
    send_message_with_keyboard(chat_id, entity_title, reply_markup={'inline_keyboard': keyboard}, language=language, link_preview_options=link_preview_options)


def send_app_list_keyboard(chat_id, communities, language):
    keyboard = []
    for community in communities:
        keyboard.append([{'text': community['name'], 'url': WEB_APP_LINK + f"?startapp={community['id']}"}])
    send_message_with_keyboard(chat_id, 'communities_app_list', reply_markup={'inline_keyboard': keyboard}, language=language)
    

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
        'protect_content': True,
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

def send_advertise_setup_keyboard(chat_id, language):
    translations = {
        'en': {
            'setup_advertising': "Start"
        },
        'ru': {
            'setup_advertising': "Начать"
        }
    }
    keyboard = [
        [{'text': translations[language]['setup_advertising'], 'url': WEB_APP_LINK + f"?startapp=advertise"}],
    ]
    send_message_with_keyboard(chat_id, 'advertise_setup', reply_markup={'inline_keyboard': keyboard}, language=language)

def send_message_with_keyboard(chat_id, text_key, reply_markup=None, language='en', link_preview_options=None):
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
            'bot_has_no_administrator_rights': "Bot has no administrator rights. Please add the bot to the chat as an administrator and try again.",
            'communities_app_list': "Communities List",
            'advertise_setup': "Setup advertising",
        },
        'ru': {
            'please_select_chat': "Пожалуйста, выберите чат:",
            'community_not_found': "Сообщество не найдено для указанного чата. Пожалуйста, создайте новое сообщество используя команду /create.",
            'successfully_joined': "Вы успешно присоединились к сообществу!",
            'community_already_exists': "Сообщество уже существует для указанного чата.",
            'community_created': "Сообщество успешно создано!",
            'bot_has_no_administrator_rights': "Бот не имеет прав администратора. Пожалуйста, добавьте бота в чат как администратора и попробуйте снова.",
            'communities_app_list': "Список Сообществ",
            'advertise_setup': "Настройка рекламы",
        }
    }

    text = translations[language].get(text_key, text_key)  # Default to text_key if not found

    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'protect_content': True,
    }
    if reply_markup:
        payload['reply_markup'] = reply_markup
    if link_preview_options:
        payload['link_preview_options'] = link_preview_options
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
    blob.upload_from_string(file_content, content_type="image/jpg")
    
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

def get_chat_administrators(chat_id):
    url = f"{TELEGRAM_API_URL}/getChatAdministrators"
    params = {"chat_id": chat_id}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()['result']
    else:
        logger.error(f"Failed to get chat administrators: {response.text}")
        return None

def get_chat_member(chat_id, user_id):
    url = f"{TELEGRAM_API_URL}/getChatMember"
    params = {"chat_id": chat_id, "user_id": user_id}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()['result']
    else:
        logger.error(f"Failed to get chat member: {response.text}")
        return None


def handle_entity_creation_from_hashtag(message, community, is_caption, is_private):
    text = message['caption'] if is_caption else message['text']
    user_id = message['from']['id']

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
            elif key == 'communityId':
                extracted_info[key] = community['id']
            elif key == 'messageId':
                extracted_info[key] = message['message_id'] if not is_private else None
            elif key == 'mediaGroupId':
                extracted_info[key] = message.get('media_group_id') if message.get('media_group_id') else default_value()
            else:
                extracted_info[key] = default_value()

    media_group_id = extracted_info.get('mediaGroupId')
    image_url = process_image_or_document(message, community['id'])
    if image_url:
        service_manager.create_media_group(media_group_id, [image_url])

    # Process the extracted_info
    try:
        if entity_type == 'event':
            entity = service_manager.create_event(**extracted_info)
        elif entity_type == 'news':
            entity = service_manager.create_news(**extracted_info)
        elif entity_type == 'item':
            entity = service_manager.create_item(**extracted_info)
        elif entity_type == 'service':
            entity = service_manager.create_service(**extracted_info)
        
        logger.info(f"Processed {entity_type} for community: {community['id']}")
        set_message_reaction(message['chat']['id'], message['message_id'], "⚡")
        return entity, image_url
    except Exception as e:
        logger.error(f"Error processing {entity_type}: {str(e)}", exc_info=True)

def set_bot_commands():
    """
    Set bot commands for different languages
    """
    base_url = f"{TELEGRAM_API_URL}/setMyCommands"
    
    commands = {
        'en': [
            {'command': 'join', 'description': 'Join a community'},
            {'command': 'create', 'description': 'Create a new community'},
            {'command': 'list', 'description': 'List communities that you are a member of'},
            {'command': 'advertise', 'description': 'Setup advertising for nearby communities'},
            # Add more commands as needed
        ],
        'ru': [
            {'command': 'join', 'description': 'Присоединиться к сообществу'},
            {'command': 'create', 'description': 'Создать новое сообщество'},
            {'command': 'list', 'description': 'Список собществ, в которых вы состоите'},
            {'command': 'advertise', 'description': 'Настройка рекламы для близлежащих сообществ'},
            # Add more commands as needed
        ],
        # Add more languages as needed
    }
    
    for language_code, command_list in commands.items():
        data = {
            'commands': command_list,
            'language_code': language_code
        }
        
        try:
            response = requests.post(base_url, json=data)
            if response.status_code == 200:
                logger.info(f"Successfully set commands for language: {language_code}")
            else:
                logger.error(f"Failed to set commands for language {language_code}. Response: {response.text}")
        except Exception as e:
            logger.error(f"Error setting commands for language {language_code}: {str(e)}")

def get_supported_language(language_code):
    return 'en' if language_code not in ['en', 'ru'] else language_code

def is_language_supported(language):
    return language in ['en', 'ru']

def is_currency_supported(currency):
    return currency in ['USD', 'EUR', 'RUB']


def calculate_distance(lat1, lon1, lat2, lon2):
    # Radius of Earth in kilometers
    R = 6371.0
        
    # Convert coordinates to radians
    lat1, lon1 = radians(lat1), radians(lon1)
    lat2, lon2 = radians(lat2), radians(lon2)
        
    # Differences in coordinates
    dlat = lat2 - lat1
    dlon = lon2 - lon1
        
    # Haversine formula
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
        
    # Calculate distance
    distance = R * c
    return distance

def is_location_in_range(location, coordinates, range):
    # Check if any coordinate is within range
    for coord in coordinates:
        if not coord.get('lat') or not coord.get('lng'):
            continue
            
        distance = calculate_distance(
            location['lat'], location['lng'],
            coord['lat'], coord['lng']
        )
        
        # Since both distance and range are in kilometers, this comparison is correct
        if distance <= range:
            return True
            
    return False

def format_gcs_filename(filename):
    """
    Format filename to be GCS-safe by:
    1. Converting to lowercase
    2. Removing special characters except dash and underscore
    3. Replacing spaces with dashes
    4. Ensuring it ends with an image extension
    """
    # Convert to lowercase
    filename = filename.lower()
    
    # Get the extension if it exists
    name, ext = os.path.splitext(filename)
    
    # Remove special characters except dash and underscore
    name = re.sub(r'[^a-z0-9-_]', '-', name)
    
    # Replace multiple dashes with single dash
    name = re.sub(r'-+', '-', name)
    
    # Remove leading and trailing dashes
    name = name.strip('-')
    
    # If no valid extension, default to .jpg
    valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif', '.svg'}
    if not ext or ext.lower() not in valid_extensions:
        ext = '.jpg'
    
    return f"{name}{ext}"

def generate_gcs_upload_link_for_image(image_name):
    formatted_name = format_gcs_filename(image_name)
    gcs_object_id = "ad-images/" + str(uuid.uuid4()) + "_" + formatted_name
    
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(gcs_object_id)

    try:
        # Get default credentials and verify them
        credentials, _ = google.auth.default()
        # Perform a refresh request to get the access token of the current credentials (Else, it's None)
        from google.auth.transport import requests
        r = requests.Request()
        credentials.refresh(r)

        gcs_upload_link = blob.generate_signed_url(
            version="v4",
            expiration=600,  # 10 minutes
            method="PUT",
            content_type="image/jpg",
            service_account_email=credentials.service_account_email,
            access_token=credentials.token
        )
        logger.info("Successfully generated signed URL")

    except Exception as e:
        logger.error(f"Failed to generate signed URL: {str(e)}", exc_info=True)
        raise

    gcs_public_url = blob.public_url
    return gcs_public_url, gcs_upload_link

def check_file_exists_in_gcs(public_url):
    """Check if a file exists in GCS"""
    if not public_url.startswith('https://storage.googleapis.com/'):
        return None
    
    # Remove the storage.googleapis.com prefix
    path = public_url.replace('https://storage.googleapis.com/', '')
    # Split into bucket and blob path
    bucket_name, blob_path = path.split('/', 1)
    
    bucket = storage_client.bucket(bucket_name)
    return bucket.blob(blob_path).exists()