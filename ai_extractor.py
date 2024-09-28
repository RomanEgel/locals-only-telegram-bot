import openai
import logging
import json
from datetime import datetime, date
from service import BaseEntity
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY
logger = logging.getLogger(__name__)

def get_confidence_threshold():
    return 30

def get_language_display_name(language_code):
    language_map = {
        'en': 'English',
        'ru': 'Russian'
    }
    return language_map.get(language_code, 'Unknown')

def extract_entity_info_with_ai(text, existing_categories, community_name, entity_class, language):
    """
    Extract entity information from text using OpenAI.
    Only return the extracted info if the confidence score is above the threshold.
    """
    logger.info(f"Existing categories: {existing_categories}")
    confidence_threshold = get_confidence_threshold()
    language_display_name = get_language_display_name(language)

    structure = entity_class.get_structure()
    description = entity_class.get_description()

    # Identify fields to be extracted by AI
    ai_structure = {k: v for k, v in structure.items() if v[2]}

    # Check if all fields have description and example
    for key, value in ai_structure.items():
        if len(value) < 5 or not value[3] or not value[4]:
            raise ValueError(f"Field '{key}' is missing description or example")

    # Get the current date
    current_date = datetime.now().isoformat()

    # Construct the prompt for OpenAI
    prompt = f"""
    Extract the following information from the given text for {description}:
    {', '.join(ai_structure.keys())}

    Only extract information that is explicitly stated in the text. Do not make assumptions or generate content that isn't present. If a field cannot be filled with information from the text, use null.

    Respect the following descriptions, examples, and data types for each field:
    {{
    {json.dumps({k: f"{v[3]}; {v[4]}. Type: {v[0].__name__}" for k, v in ai_structure.items()}, indent=2)}
    }}

    Important: For date fields, use the ISO format "YYYY-MM-DDTHH:MM:SS".
    
    Categories to take into account: {existing_categories}. If any of the categories match the text exactly - use it. But if you're not certain or if it's only partially related - come up with a new category. 
    Example: Categories: ['Clothes'], and text about gopro with accessories like handle, batteries, etc - you should come up with a new category 'Electronics'.
    Example: Categories: ['Electronics'], and text about a new iPhone 15 - you should use existing category 'Electronics'.

    The current date is {current_date}.
    Also, provide a confidence score (0-100) indicating how well the extracted information matches the given text. Lower the score if many fields are null.

    Text: {text}

    Response format:
    {{
        "extracted_info": {{
            "field1": value1,
            "field2": null,
            ...
        }},
        "confidence_score": 85
    }}

    Respond only with the JSON, no additional text. Use null for any field that cannot be determined from the given text.

    Note: The extracted values MUST be in {language_display_name}.
    """

    # Call OpenAI API
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini", 
        messages=[
            {"role": "system", "content": f"You are a helpful assistant that extracts structured information from text. The text is a message from a Telegram user who is part of the '{community_name}' community. Keep that in mind when extracting information."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
    )

    # Log the raw OpenAI response
    logger.info(f"Raw OpenAI response: {response.choices[0].message.content}")

    # Parse the response
    try:
        # First, replace the tuple representation with a list
        content = response.choices[0].message.content
        content = content.replace("(", "[").replace(")", "]")
        
        result = json.loads(content)
        extracted_info = result['extracted_info']
        confidence_score = result['confidence_score']

        # Log the confidence score
        logger.info(f"Confidence score for {entity_class.__name__}: {confidence_score}")

        # Remove fields with null values
        extracted_info = {k: v for k, v in extracted_info.items() if v is not None}

        # Check if confidence score is above the threshold
        if confidence_score < confidence_threshold:
            logger.warning(f"Confidence score {confidence_score} is below threshold {confidence_threshold}")
            return None

        # Ensure all fields are present in the extracted info and have the correct type
        for key, (value_type, _, _, _, _) in ai_structure.items():
            if key in extracted_info:
                # Convert the value to the correct type
                try:
                    if value_type == datetime:
                        extracted_info[key] = datetime.fromisoformat(extracted_info[key])
                    elif value_type in (int, float, bool, str):
                        extracted_info[key] = value_type(extracted_info[key])
                    elif value_type == list:
                        if isinstance(extracted_info[key], str):
                            # Handle the case where a list is represented as a string
                            extracted_info[key] = json.loads(extracted_info[key].replace("'", '"'))
                        elif not isinstance(extracted_info[key], list):
                            extracted_info[key] = [extracted_info[key]]
                    elif value_type == dict and not isinstance(extracted_info[key], dict):
                        extracted_info[key] = {"value": extracted_info[key]}
                except (ValueError, json.JSONDecodeError) as e:
                    logger.warning(f"Could not convert {key} to {value_type}. Error: {e}. Skipping field.")
                    del extracted_info[key]

        return extracted_info
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        logger.error(f"Problematic content: {response.choices[0].message.content}")
        return None
    except Exception as e:
        logger.error(f"Error parsing OpenAI response: {e}")
        return None