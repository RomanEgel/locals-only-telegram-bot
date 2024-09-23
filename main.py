import functions_framework
from flask import Flask, request
import logging
from oauth import oauth_blueprint

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.register_blueprint(oauth_blueprint)

@functions_framework.http
def main(request):
    """
    HTTP Cloud Function entry point.
    This function will handle all incoming requests and route them to the appropriate Flask endpoint.
    """
    if request.method == 'OPTIONS':
        # Handle preflight requests
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    # Set CORS headers for the main request
    headers = {
        'Access-Control-Allow-Origin': '*'
    }

    # Handle the main request
    try:
        with app.request_context(request.environ):
            rv = app.dispatch_request()
        response = app.make_response(rv)
        return (response.get_data(), response.status_code, headers)
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}", exc_info=True)
        return (str(e), 500, headers)