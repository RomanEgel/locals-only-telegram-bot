from flask import Blueprint, request, jsonify
import os
import logging
import requests
from config import service_manager

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

def send_message(chat_id, text):
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

def handle_command(message, command):
    """
    Handle bot commands.
    """
    chat_id = message['chat']['id']
    # Check if the community exists, if not, create it
    community = service_manager.get_community_by_chat_id(chat_id)
    if not community:
        community = service_manager.create_community(chat_id, message['chat']['title'])
        logger.info(f"Created new community for chat_id: {chat_id}")

    # Extract the command without the bot name if it includes '@'
    command = command.split('@')[0]

    logger.info(f"Handling command: {command} for chat_id: {chat_id}")

    if command == '/start':
        send_message(chat_id, "Welcome to the bot!")
    elif command == '/help':
        send_message(chat_id, "Here are the available commands: /start, /help, /app")
    elif command == '/app':
        send_inline_keyboard(chat_id, "Community App", WEB_APP_LINK + f"?startapp={chat_id}")

def send_inline_keyboard(chat_id, text, url):
    """
    Send a message with an inline keyboard button.
    """
    api_url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'reply_markup': {
            'inline_keyboard': [[
                {
                    'text': "Open Web App",
                    'url': url
                }
            ]]
        }
    }
    response = requests.post(api_url, json=payload)
    return response.json()
