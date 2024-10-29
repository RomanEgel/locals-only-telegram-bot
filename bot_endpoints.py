from flask import Blueprint, request, jsonify
import logging
from group_handler import handle_group_message
from private_handler import handle_private_message

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the Blueprint
bot_blueprint = Blueprint('bot', __name__)

@bot_blueprint.route("/bot", methods=['POST'])
def handle_telegram_event():
    """
    Handle incoming Telegram events.
    """
    try:
        event = request.get_json()
        logger.info(f"Received event: {event}")

        if 'message' in event:
            message = event['message']
            chat_type = message['chat']['type']
            
            if chat_type in ['group', 'supergroup']:
                handle_group_message(message)
            elif chat_type == 'private':
                handle_private_message(message)
            else:
                logger.info(f"Unsupported chat type: {chat_type}")
    except Exception as e:
        logger.error(f"Error handling Telegram event: {str(e)}", exc_info=True)
    
    return jsonify({"status": "ok"}), 200