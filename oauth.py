from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
import os
import hashlib
import hmac
from urllib.parse import parse_qsl
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Define the Blueprint
oauth_blueprint = Blueprint('oauth', __name__)

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
    return {parsed_data, hmac.compare_digest(data_check_hash, hash_value)}

@oauth_blueprint.route("/oauth/validate", methods=['POST', 'OPTIONS'])
@cross_origin(origins="*", allow_headers=["Content-Type", "Authorization"])
def validate_telegram_init_data():
    """
    Validate the InitData received from Telegram mini app.
    """
    if request.method == 'OPTIONS':
        # Preflight request. Reply successfully:
        return jsonify({"message": "Preflight request successful"}), 200

    auth_header = request.headers.get('Authorization')
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')

    if not auth_header or not auth_header.startswith('tma '):
        return jsonify({"error": "Missing or invalid Authorization header"}), 400

    init_data = auth_header[4:]  # Remove 'tma ' prefix

    if not bot_token:
        return jsonify({"error": "Bot token not configured"}), 500

    try:
        logger.info(f"Validating init data: {init_data}")
        parsed_data, is_valid = validate_init_data(init_data, bot_token)
        logger.info(f"Init data validation result: {is_valid}")
        return jsonify({"valid": is_valid, "community": {"name": "Lisbon Surfing"}, "user": {"name": "Roman"}})
    except Exception as e:
        logger.error(f"Error validating init data: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400