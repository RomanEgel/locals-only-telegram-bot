import uuid
from pymongo import MongoClient, ReturnDocument
import os
from bson import ObjectId, Int64
from datetime import datetime
import json
from typing import List

class BaseEntity:
    def __init__(self, db, collection_name):
        self.collection = db[collection_name]

    @classmethod
    def get_structure(cls):
        return {
            "id": (str, lambda: str(uuid.uuid4()), False, None, None),
            "title": (str, lambda: "Untitled", True, None, None),
            "mediaGroupId": (str, lambda: str(uuid.uuid4()), False, None, None),
            "author": (str, lambda: None, False, None, None),
            "userId": (int, lambda: None, False, None, None),
            "category": (str, lambda: "Uncategorized", True, None, None),
            "description": (str, lambda: "No description provided", True, None, None),
            "publishedAt": (datetime, lambda: datetime.now(), False, None, None),
            "communityId": (str, lambda: None, False, None, None),
            "messageId": (str, lambda: None, False, None, None)
        }

    def create(self, id, title, author, userId, publishedAt, category, description, communityId, messageId, **kwargs):
        entity = {
            "_id": id,
            "title": title,
            "author": author,
            "userId": userId,
            "publishedAt": publishedAt,
            "category": category,
            "description": description,
            "communityId": communityId,
            "messageId": messageId
        }
        entity.update(kwargs)
        self.collection.insert_one(entity)
        return format_entity(entity)

    def get_by_id(self, id):
        entity = self.collection.find_one({"_id": id})
        return format_entity(entity) if entity else None

    def search(self, communityId):
        return [format_entity(entity) for entity in self.collection.find({"communityId": communityId})]
    
    def get_categories_by_community_id(self, communityId):
        categories = self.collection.distinct("category", {"communityId": communityId})
        return categories

    def delete(self, id, communityId, userId):
        deleted_entity = self.collection.find_one_and_delete(
            {"_id": id, "communityId": communityId, "userId": userId},
            return_document=ReturnDocument.BEFORE
        )
        
        return format_entity(deleted_entity)
    
    def update(self, id, communityId, userId, **kwargs):
        # Filter out None values from kwargs
        update_fields = {k: v for k, v in kwargs.items() if v is not None}
        
        # If there are no non-None values, return existing entity
        if not update_fields:
            updated_entity = self.collection.find_one({"_id": id, "communityId": communityId, "userId": userId})
        else:
            # Update the document
            updated_entity = self.collection.find_one_and_update(
                {"_id": id, "communityId": communityId, "userId": userId},
                {"$set": update_fields},
                return_document=ReturnDocument.AFTER
            )

        return format_entity(updated_entity)

class LocalsCommunity:
    def __init__(self, db):
        self.collection = db['communities']

    def get_by_id(self, communityId):
        community = self.collection.find_one({"_id": communityId})
        if community:
            return format_entity(community)
        return None

    def get_by_chat_id(self, chatId):
        community = self.collection.find_one({"chatId": chatId})
        return format_entity(community) if community else None

    def create(self, chatId, name, language="en"):
        community = {
            "_id": str(uuid.uuid4()),
            "chatId": chatId,
            "name": name,
            "language": language,
            "status": "SETUP",  # Add status field with initial value "SETUP"
        }
        self.collection.insert_one(community)
        
        return format_entity(community)

    def update(self, communityId, update_data):
        community = self.collection.find_one_and_update(
            {"_id": communityId},
            {"$set": update_data},
            return_document=ReturnDocument.AFTER
        )
        return format_entity(community) if community else None
    
    def find_all(self):
        return [format_entity(entity) for entity in self.collection.find()]

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
            "description": (str, lambda: "No description provided", True, "A detailed description of the item, including condition, features, etc. Use all provided information to describe the item.", "")
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
            "description": (str, lambda: "No description provided", True, "A detailed description of the service, including what's offered, experience level, etc. Use all provided information to describe the service.", "")
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
            "date": (datetime, lambda: datetime.now(), True, "The date and time when the event will take place (always in the future from the current date). Use ISO format.", "Format: 'YYYY-MM-DDThh:mm:ss'"),
            "category": (str, lambda: "Uncategorized", True, "The category the event belongs to.", "Examples: 'Community Service', 'Arts & Culture', 'Sports & Recreation', 'Education'"),
            "description": (str, lambda: "No description provided", True, "A detailed description of the event, including what to expect, who should attend, etc. Use all provided information to describe the event.", "")
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
            "description": (str, lambda: "No description provided", True, "The main content of the news item, including key details and quotes if available. Use all provided information to describe the news item.", "")
        })
        return structure

    @classmethod
    def get_description(cls):
        return "a news item relevant to the local community"

class LocalsUser:
    def __init__(self, db):
        self.collection = db['users']

    def create(self, id: int, communities: List[str] = None, chatId: int = None):
        user = {
            "_id": Int64(id),
            "communities": communities or [],
            "chatId": chatId and Int64(chatId) or None,
            "notificationsEnabled": False
        }
        self.collection.insert_one(user)
        return format_entity(user)
    
    def set_chat_id(self, id: int, chatId: int):
        self.collection.update_one({"_id": Int64(id)}, {"$set": {"chatId": Int64(chatId)}})

    def set_notifications_enabled(self, id: int, notificationsEnabled: bool):
        self.collection.update_one({"_id": Int64(id)}, {"$set": {"notificationsEnabled": notificationsEnabled}})

    def get_by_id(self, user_id: int):
        user = self.collection.find_one({"_id": Int64(user_id)})
        return format_entity(user) if user else None

    def search(self, community_id: str, filter: dict = None):
        return [format_entity(entity) for entity in self.collection.find({"communities": community_id, **(filter or {})})]

    def add_community(self, user_id: int, community_id: str):
        result = self.collection.update_one(
            {"_id": Int64(user_id)},
            {"$addToSet": {"communities": community_id}},
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None

    def remove_community(self, user_id: int, community_id: str):
        result = self.collection.update_one(
            {"_id": Int64(user_id)},
            {"$pull": {"communities": community_id}}
        )
        return result.modified_count > 0

class MediaGroup:
    def __init__(self, db):
        self.collection = db['media_groups']

    def create(self, id: str, images: List[str]):
        media_group = {
            "_id": id,
            "images": images
        }
        self.collection.insert_one(media_group)
        return format_entity(media_group)

    def add_image(self, id: str, image: str):
        self.collection.update_one({"_id": id}, {"$push": {"images": image}})

    def get_by_ids(self, ids: List[str]):
        return [format_entity(entity) for entity in self.collection.find({"_id": {"$in": ids}})]
    
    def delete(self, id: str):
        self.collection.delete_one({"_id": id})

class LocalsAdvertisement:
    def __init__(self, db):
        self.collection = db['advertisements']
        self.collection.create_index([("geoLocation", "2dsphere")])
    
    def format_ad_entity(self, advertisement):
        advertisement.pop('geoLocation', None)
        return format_entity(advertisement)

    def create(self, userId: int, mediaGroupId: str, location: dict, range: int, entityType: str, title: str, description: str, price: float, currency: str):
        advertisement = {
            "_id": str(uuid.uuid4()),
            "userId": userId,
            "mediaGroupId": mediaGroupId,
            "location": location,
            "geoLocation": {
                "type": "Point",
                "coordinates": [location['lng'], location['lat']]
            },
            "range": range,
            "entityType": entityType,
            "createdAt": datetime.now(),
            "title": title,
            "description": description,
            "price": price,
            "currency": currency
        }
        self.collection.insert_one(advertisement)
        return self.format_ad_entity(advertisement)

    def find_by_user_id(self, userId: int):
        return [self.format_ad_entity(entity) for entity in self.collection.find({"userId": userId})]
    
    def find_for_location(self, location: dict):
        pipeline = [
            {
                "$geoNear": {
                    "near": {"type": "Point", "coordinates": [location['lng'], location['lat']]},
                    "distanceField": "distance",
                    "spherical": True
                }
            },
            {
                "$addFields": {
                    "distanceInKm": {"$divide": ["$distance", 1000]}  # Convert distance from meters to kilometers
                }
            },
            {
                "$match": {
                    "$expr": {"$lte": ["$distanceInKm", "$range"]}
                }
            }
        ]
        
        advertisements = self.collection.aggregate(pipeline)
        return [self.format_ad_entity(ad) for ad in advertisements]

    def delete(self, id: str, userId: int):
        deleted_advertisement = self.collection.find_one_and_delete({"_id": id, "userId": userId}, return_document=ReturnDocument.BEFORE)
        return self.format_ad_entity(deleted_advertisement) if deleted_advertisement else None

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
        self.user = LocalsUser(db)  # Add this line
        self.media_group = MediaGroup(db)  # Add this line
        self.advertisement = LocalsAdvertisement(db)

    def get_community_by_id(self, communityId):
        return self.community.get_by_id(communityId)

    def get_community_by_chat_id(self, chatId):
        return self.community.get_by_chat_id(chatId)

    def create_community(self, chatId, title, language='en'):
        return self.community.create(chatId, title, language)

    def update_community(self, communityId, update_data):
        return self.community.update(communityId, update_data)
    
    def get_all_communities(self):
        return self.community.find_all()

    def create_item(self, id, title, price, currency, author, userId, publishedAt, category, description, communityId, messageId, mediaGroupId):
        return self.item.create(id, title, author, userId, publishedAt, category, description, communityId, messageId, price=price, currency=currency, mediaGroupId=mediaGroupId)

    def search_items(self, communityId):
        return self.item.search(communityId)
    
    def get_item_categories_by_community_id(self, communityId):
        return self.item.get_categories_by_community_id(communityId)
    
    def update_item(self, id, communityId, userId, title, description, price, currency, category):
        return self.item.update(id, communityId, userId, title=title, description=description, price=price, currency=currency, category=category)

    def delete_item(self, id, communityId, userId):
        return self.item.delete(id, communityId, userId)

    def create_service(self, id, title, price, currency, author, userId, publishedAt, category, description, communityId, messageId, mediaGroupId):
        return self.service.create(id, title, author, userId, publishedAt, category, description, communityId, messageId, price=price, currency=currency, mediaGroupId=mediaGroupId)

    def search_services(self, communityId):
        return self.service.search(communityId)
    
    def get_service_categories_by_community_id(self, communityId):
        return self.service.get_categories_by_community_id(communityId)
    
    def update_service(self, id, communityId, userId, title, description, price, currency, category):
        return self.service.update(id, communityId, userId, title=title, description=description, price=price, currency=currency, category=category)

    def delete_service(self, id, communityId, userId):
        return self.service.delete(id, communityId, userId)

    def create_event(self, id, title, date, author, userId, publishedAt, category, description, communityId, messageId, mediaGroupId):
        return self.event.create(id, title, author, userId, publishedAt, category, description, communityId, messageId, date=date, mediaGroupId=mediaGroupId)

    def search_events(self, communityId):
        return self.event.search(communityId)
    
    def get_event_categories_by_community_id(self, communityId):
        return self.event.get_categories_by_community_id(communityId)
    
    def update_event(self, id, communityId, userId, title, description, date, category):
        return self.event.update(id, communityId, userId, title=title, description=description, date=date, category=category)
    
    def delete_event(self, id, communityId, userId):
        return self.event.delete(id, communityId, userId)

    def create_news(self, id, title, author, userId, publishedAt, category, description, communityId, messageId, mediaGroupId):
        return self.news.create(id, title, author, userId, publishedAt, category, description, communityId, messageId, mediaGroupId=mediaGroupId)

    def search_news(self, communityId):
        return self.news.search(communityId)
    
    def get_news_categories_by_community_id(self, communityId):
        return self.news.get_categories_by_community_id(communityId)
    
    def update_news(self, id, communityId, userId, title, description, category):
        return self.news.update(id, communityId, userId, title=title, description=description, category=category)

    def delete_news(self, id, communityId, userId):
        return self.news.delete(id, communityId, userId)
    
    def get_entity_by_id(self, entity_id):
        # Try each entity type one by one
        entity = self.item.get_by_id(entity_id)
        if entity:
            return entity, 'items'
            
        entity = self.service.get_by_id(entity_id)
        if entity:
            return entity, 'services'
            
        entity = self.event.get_by_id(entity_id)
        if entity:
            return entity, 'events'
            
        entity = self.news.get_by_id(entity_id)
        if entity:
            return entity, 'news'
            
        return None, None

    def create_user(self, user_id: int, communities: List[str], chatId: int = None):
        return self.user.create(user_id, communities, chatId)

    def get_user(self, user_id: int):
        return self.user.get_by_id(user_id)

    def add_user_to_community(self, user_id: int, community_id: str):
        return self.user.add_community(user_id, community_id)

    def remove_user_from_community(self, user_id: int, community_id: str):
        return self.user.remove_community(user_id, community_id)

    def add_user_to_community_if_not_exists(self, user_id, community_id):
        user = self.get_user(user_id)
        if not user:
            self.create_user(user_id, [community_id])
        elif community_id not in user['communities']:
            self.add_user_to_community(user_id, community_id)
        return user

    def set_user_notifications_enabled(self, id: int, notificationsEnabled: bool):
        return self.user.set_notifications_enabled(id, notificationsEnabled)

    def search_users_in_community(self, community_id: str, filter: dict = None):
        return self.user.search(community_id, filter)
    
    def set_user_chat_id(self, id: int, chatId: int):
        return self.user.set_chat_id(id, chatId)

    def create_media_group(self, id: str, images: List[str]):
        return self.media_group.create(id, images)

    def add_image_to_media_group(self, id: str, new_image: str):
        return self.media_group.add_image(id, new_image)

    def get_media_groups(self, ids: List[str]):
        return self.media_group.get_by_ids(ids)
    
    def delete_media_group(self, id: str):
        return self.media_group.delete(id)
    
    def create_advertisement(self, userId: int, mediaGroupId: str, location: dict, range: int, entityType: str, title: str, description: str, price: float, currency: str):
        return self.advertisement.create(userId, mediaGroupId, location, range, entityType, title, description, price, currency)
    
    def find_advertisements_by_user_id(self, userId: int):
        return self.advertisement.find_by_user_id(userId)
    
    def find_advertisements_for_location(self, location: dict):
        return self.advertisement.find_for_location(location)
    
    def delete_advertisement(self, id: str, userId: int):
        return self.advertisement.delete(id, userId)


def format_entity(entity):
    entity['id'] = str(entity['_id'])
    entity.pop('_id', None)
    return entity