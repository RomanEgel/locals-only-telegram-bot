import os
from service import ServiceManager
from google.cloud import storage

# Initialize the ServiceManager
service_manager = ServiceManager()

# Initialize Google Cloud Storage client
storage_client = storage.Client()

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')