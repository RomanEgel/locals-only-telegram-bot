import uuid
from pymongo import MongoClient, ReturnDocument
import os
from bson import ObjectId
from datetime import datetime
import json

class BaseEntity:
    def __init__(self, db, collection_name):
        self.collection = db[collection_name]

    @classmethod
    def get_structure(cls):
        return {
            "id": (str, lambda: str(uuid.uuid4()), False, None, None),
            "title": (str, lambda: "Untitled", True, None, None),
            "image": (str, lambda: None, False, None, None),
            "author": (str, lambda: None, False, None, None),
            "username": (str, lambda: None, False, None, None),  # Add username
            "category": (str, lambda: "Uncategorized", True, None, None),
            "description": (str, lambda: "No description provided", True, None, None),
            "publishedAt": (datetime, lambda: datetime.now(), False, None, None),
            "communityId": (int, lambda: None, False, None, None),
            "messageId": (str, lambda: None, False, None, None)  # Add messageId
        }

    def create(self, id, title, image, author, username, publishedAt, category, description, communityId, messageId, **kwargs):
        entity = {
            "id": id,
            "title": title,
            "image": image,
            "author": author,
            "username": username,  # Add username
            "publishedAt": publishedAt,
            "category": category,
            "description": description,
            "communityId": communityId,
            "messageId": messageId  # Add messageId
        }
        entity.update(kwargs)
        self.collection.insert_one(entity)
        return entity

    def search(self, communityId):
        entities = list(self.collection.find({"communityId": communityId}))
        for entity in entities:
            entity['_id'] = str(entity['_id'])
        return entities

    def delete(self, id, communityId, username):
        deleted_entity = self.collection.find_one_and_delete(
            {"id": id, "communityId": communityId, "username": username},
            return_document=ReturnDocument.BEFORE
        )
        deleted_entity['_id'] = str(deleted_entity['_id'])
        return deleted_entity
    
    def update(self, id, chat_id, username, **kwargs):
        # Filter out None values from kwargs
        update_fields = {k: v for k, v in kwargs.items() if v is not None}
        
        # If there are no non-None values, return existing entity
        if not update_fields:
            updated_entity = self.collection.find_one({"id": id, "communityId": chat_id, "username": username})
        else:
            # Update the document
            updated_entity = self.collection.find_one_and_update(
                {"id": id, "communityId": chat_id, "username": username},
                {"$set": update_fields},
                return_document=ReturnDocument.AFTER
            )

        updated_entity['_id'] = str(updated_entity['_id'])
        return updated_entity

class LocalsCommunity:
    def __init__(self, db):
        self.collection = db['communities']

    def get_by_chat_id(self, chatId):
        return self.collection.find_one({"chatId": chatId})

    def create(self, chatId, name, language="en"):
        community = {
            "chatId": chatId,
            "name": name,
            "language": language,
            "status": "SETUP"  # Add status field with initial value "SETUP"
        }
        self.collection.insert_one(community)
        return community

    def update(self, chatId, update_data):
        return self.collection.find_one_and_update(
            {"chatId": chatId},
            {"$set": update_data},
            return_document=ReturnDocument.AFTER
        )

    def set_ready(self, chatId):
        return self.update(chatId, {"status": "READY"})

class LocalsItem(BaseEntity):
    def __init__(self, db):
        super().__init__(db, 'items')

    @classmethod
    def get_structure(cls):
        structure = super().get_structure()
        structure.update({
            "price": (float, lambda: None, True, "The price of the item. Extract a numeric value. If it's mentioned as free, use 0.", "Examples: 10.99, 500, 1500.50"),
            "currency": (str, lambda: None, True, "The currency code for the price. Use standard 3-letter currency codes.", "Examples: USD, EUR, GBP, RUB"),
            "title": (str, lambda: "Untitled", True, "A short, descriptive title for the item.", "Examples: 'Vintage Guitar', 'iPhone 12 Pro', 'Handmade Pottery Set'"),
            "category": (str, lambda: "Uncategorized", True, "The category the item belongs to. Use general terms.", "Examples: 'Electronics', 'Furniture', 'Clothing', 'Books'"),
            "description": (str, lambda: "No description provided", True, "A detailed description of the item, including condition, features, etc.", "Example: 'Lightly used iPhone 12 Pro, 256GB, Pacific Blue. Comes with original box and accessories. Minor scratches on the back.'")
        })
        return structure

    @classmethod
    def get_description(cls):
        return "an item for sale or giveaway in the local community"

class LocalsService(BaseEntity):
    def __init__(self, db):
        super().__init__(db, 'services')

    @classmethod
    def get_structure(cls):
        structure = super().get_structure()
        structure.update({
            "price": (float, lambda: None, True, "The price of the service. Extract a numeric value. Use per hour rate if applicable. If it's mentioned as free, use 0.", "Examples: 25.50, 100, 75.99"),
            "currency": (str, lambda: None, True, "The currency code for the price. Use standard 3-letter currency codes.", "Examples: USD, EUR, GBP, RUB"),
            "title": (str, lambda: "Untitled", True, "A short, descriptive title for the service.", "Examples: 'Professional Photography', 'House Cleaning', 'Math Tutoring'"),
            "category": (str, lambda: "Uncategorized", True, "The category the service belongs to. Use general terms.", "Examples: 'Home Services', 'Education', 'Professional Services', 'Health & Wellness'"),
            "description": (str, lambda: "No description provided", True, "A detailed description of the service, including what's offered, experience level, etc.", "Example: 'Experienced math tutor offering one-on-one lessons for high school and college students. Specializing in calculus and algebra. Flexible scheduling available.'")
        })
        return structure

    @classmethod
    def get_description(cls):
        return "a service offered by a community member"

class LocalsEvent(BaseEntity):
    def __init__(self, db):
        super().__init__(db, 'events')

    @classmethod
    def get_structure(cls):
        structure = super().get_structure()
        structure.update({
            "title": (str, lambda: "Untitled", True, "A short, descriptive title for the event.", "Examples: 'Community Cleanup Day', 'Local Art Exhibition', 'Neighborhood BBQ'"),
            "date": (datetime, lambda: datetime.now(), True, "The date and time when the event will take place. Use ISO format.", "Examples: '2023-07-15T14:00:00', '2023-08-01T09:30:00'"),
            "category": (str, lambda: "Uncategorized", True, "The category the event belongs to.", "Examples: 'Community Service', 'Arts & Culture', 'Sports & Recreation', 'Education'"),
            "description": (str, lambda: "No description provided", True, "A detailed description of the event, including what to expect, who should attend, etc.", "Example: 'Join us for our annual community cleanup day. We'll meet at the park entrance at 9 AM. Gloves and trash bags will be provided. Lunch will be served for all volunteers.'")
        })
        return structure

    @classmethod
    def get_description(cls):
        return "an event happening in the local community"

class LocalsNews(BaseEntity):
    def __init__(self, db):
        super().__init__(db, 'news')

    @classmethod
    def get_structure(cls):
        structure = super().get_structure()
        structure.update({
            "title": (str, lambda: "Untitled", True, "A short, descriptive headline for the news item.", "Examples: 'New Community Center Opening Next Month', 'Local School Wins State Championship'"),
            "category": (str, lambda: "Uncategorized", True, "The category the news item belongs to.", "Examples: 'Local Government', 'Education', 'Business', 'Community'"),
            "description": (str, lambda: "No description provided", True, "The main content of the news item, including key details and quotes if available.", "Example: 'The city council announced today that the new community center will open its doors on July 1st. The $5 million facility will feature a gym, swimming pool, and meeting rooms for local organizations.'")
        })
        return structure

    @classmethod
    def get_description(cls):
        return "a news item relevant to the local community"

class ServiceManager:
    def __init__(self):
        db_uri = os.environ.get('MONGODB_URI')
        db_name = os.environ.get('MONGODB_NAME')
        client = MongoClient(db_uri)
        db = client[db_name]
        self.community = LocalsCommunity(db)
        self.item = LocalsItem(db)
        self.service = LocalsService(db)
        self.event = LocalsEvent(db)
        self.news = LocalsNews(db)

    def get_community_by_chat_id(self, chatId):
        return self.community.get_by_chat_id(chatId)

    def create_community(self, chatId, title, language='en'):
        return self.community.create(chatId, title, language)

    def update_community(self, chatId, update_data):
        return self.community.update(chatId, update_data)

    def create_item(self, id, title, price, currency, image, author, username, publishedAt, category, description, communityId, messageId):
        return self.item.create(id, title, image, author, username, publishedAt, category, description, communityId, messageId, price=price, currency=currency)

    def search_items(self, communityId):
        return self.item.search(communityId)
    
    def update_item(self, id, chat_id, username, title, description, price, currency, category):
        return self.item.update(id, chat_id, username, title=title, description=description, price=price, currency=currency, category=category)

    def delete_item(self, id, communityId, username):
        return self.item.delete(id, communityId, username)

    def create_service(self, id, title, price, currency, image, author, username, publishedAt, category, description, communityId, messageId):
        return self.service.create(id, title, image, author, username, publishedAt, category, description, communityId, messageId, price=price, currency=currency)

    def search_services(self, communityId):
        return self.service.search(communityId)
    
    def update_service(self, id, chat_id, username, title, description, price, currency, category):
        return self.service.update(id, chat_id, username, title=title, description=description, price=price, currency=currency, category=category)

    def delete_service(self, id, communityId, username):
        return self.service.delete(id, communityId, username)

    def create_event(self, id, title, date, image, author, username, publishedAt, category, description, communityId, messageId):
        return self.event.create(id, title, image, author, username, publishedAt, category, description, communityId, messageId, date=date)

    def search_events(self, communityId):
        return self.event.search(communityId)
    
    def update_event(self, id, chat_id, username, title, description, date, category):
        return self.event.update(id, chat_id, username, title=title, description=description, date=date, category=category)
    
    def delete_event(self, id, communityId, username):
        return self.event.delete(id, communityId, username)

    def create_news(self, id, title, image, author, username, publishedAt, category, description, communityId, messageId):
        return self.news.create(id, title, image, author, username, publishedAt, category, description, communityId, messageId)

    def search_news(self, communityId):
        return self.news.search(communityId)
    
    def update_news(self, id, chat_id, username, title, description, category):
        return self.news.update(id, chat_id, username, title=title, description=description, category=category)

    def delete_news(self, id, communityId, username):
        return self.news.delete(id, communityId, username)
