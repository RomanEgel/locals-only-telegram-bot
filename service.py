from pymongo import MongoClient
import os
from bson import ObjectId

class LocalsCommunity:
    def __init__(self, db):
        self.collection = db['communities']

    def get_by_chat_id(self, chatId):
        return self.collection.find_one({"chatId": chatId})

    def create(self, chatId, name):
        community = {
            "chatId": chatId,
            "name": name
        }
        self.collection.insert_one(community)
        return community

class LocalsItem:
    def __init__(self, db):
        self.collection = db['items']

    def create(self, id, title, price, image, author, publishedAt, category, description, communityId):
        item = {
            "id": id,
            "title": title,
            "price": price,
            "image": image,
            "author": author,
            "publishedAt": publishedAt,
            "category": category,
            "description": description,
            "communityId": communityId
        }
        self.collection.insert_one(item)
        return item

    def search(self, communityId):
        items = list(self.collection.find({"communityId": communityId}))
        for item in items:
            item['_id'] = str(item['_id'])
        return items

class LocalsService:
    def __init__(self, db):
        self.collection = db['services']

    def create(self, id, title, price, image, author, publishedAt, category, description, communityId):
        service = {
            "id": id,
            "title": title,
            "price": price,
            "image": image,
            "author": author,
            "publishedAt": publishedAt,
            "category": category,
            "description": description,
            "communityId": communityId
        }
        self.collection.insert_one(service)
        return service

    def search(self, communityId):
        services = list(self.collection.find({"communityId": communityId}))
        for service in services:
            service['_id'] = str(service['_id'])
        return services

class LocalsEvent:
    def __init__(self, db):
        self.collection = db['events']

    def create(self, id, title, date, image, author, publishedAt, category, description, communityId):
        event = {
            "id": id,
            "title": title,
            "date": date,
            "image": image,
            "author": author,
            "publishedAt": publishedAt,
            "category": category,
            "description": description,
            "communityId": communityId
        }
        self.collection.insert_one(event)
        return event

    def search(self, communityId):
        events = list(self.collection.find({"communityId": communityId}))
        for event in events:
            event['_id'] = str(event['_id'])
        return events

class LocalsNews:
    def __init__(self, db):
        self.collection = db['news']

    def create(self, id, title, image, author, publishedAt, category, description, communityId):
        news = {
            "id": id,
            "title": title,
            "image": image,
            "author": author,
            "publishedAt": publishedAt,
            "category": category,
            "description": description,
            "communityId": communityId
        }
        self.collection.insert_one(news)
        return news

    def search(self, communityId):
        news_items = list(self.collection.find({"communityId": communityId}))
        for news in news_items:
            news['_id'] = str(news['_id'])
        return news_items

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
        self.initialize_database()  # Initialize the database with predefined entities

    def initialize_database(self):
        community_id = -1002434020920

        items = [
            {"title": "Vintage Bicycle", "price": 150, "image": "/bike.png", "author": "Alice Smith", "publishedAt": "2023-07-10 14:30", "category": "used items", "description": "Classic 1980s road bike, perfect for city commutes or weekend rides.", "communityId": community_id},
            {"title": "Handmade Pottery", "price": 50, "image": "/pottery.png", "author": "Bob Johnson", "publishedAt": "2023-07-09 10:15", "category": "handmade", "description": "Unique, hand-crafted ceramic vase with intricate floral design.", "communityId": community_id},
            {"title": "Local Honey", "price": 10, "image": "/honey.png", "author": "Carol Williams", "publishedAt": "2023-07-08 16:45", "category": "food", "description": "Pure, organic honey from local beekeepers. Great for tea or baking.", "communityId": community_id},
            {"title": "Old Books", "price": 0, "image": "/old_books.png", "author": "David Brown", "publishedAt": "2023-07-07 09:00", "category": "giveaway", "description": "Collection of classic literature books in good condition. Free to a good home.", "communityId": community_id},
        ]

        services = [
            {"title": "Gardening Services", "price": 25, "image": "/gardening.png", "author": "Eva Green", "publishedAt": "2023-07-06 11:30", "category": "maintenance", "description": "Professional garden maintenance, including mowing, pruning, and planting.", "communityId": community_id},
            {"title": "Bike Repair", "price": 40, "image": "/bike_repair.png", "author": "Frank White", "publishedAt": "2023-07-05 13:20", "category": "repair", "description": "Expert bicycle repair and tune-up service. Quick turnaround time.", "communityId": community_id},
            {"title": "House Painting", "price": 100, "image": "/house_painting.png", "author": "Grace Lee", "publishedAt": "2023-07-04 15:10", "category": "construction", "description": "Interior and exterior house painting. Quality work at competitive prices.", "communityId": community_id},
            {"title": "Babysitting", "price": 15, "image": "/baby_sitting.png", "author": "Henry Davis", "publishedAt": "2023-07-03 17:00", "category": "care", "description": "Experienced and reliable babysitter available for evenings and weekends.", "communityId": community_id},
        ]

        events = [
            {"title": "Community Cleanup", "image": "/city_cleanup.png", "date": "2023-07-15", "author": "Ivy Wilson", "publishedAt": "2023-07-02 08:45", "category": "sport", "description": "Join us for a day of cleaning up our local parks and streets. Equipment provided.", "communityId": community_id},
            {"title": "Local Art Exhibition", "image": "/local_art.png", "date": "2023-07-22", "author": "Jack Thompson", "publishedAt": "2023-07-01 14:30", "category": "art", "description": "Showcase of talented local artists featuring paintings, sculptures, and photography.", "communityId": community_id},
            {"title": "Startup Networking Event", "image": "/networking.png", "date": "2023-07-29", "author": "Karen Martinez", "publishedAt": "2023-06-30 11:20", "category": "business", "description": "Connect with local entrepreneurs and investors. Great opportunity for networking.", "communityId": community_id},
            {"title": "Group Hiking Trip", "image": "/group_hiking.png", "date": "2023-08-05", "author": "Liam Anderson", "publishedAt": "2023-06-29 16:15", "category": "travelling", "description": "Scenic 10km hike through beautiful forest trails. Suitable for all fitness levels.", "communityId": community_id},
        ]

        news = [
            {"title": "New Community Center Opening", "image": "/community_center.png", "author": "City Council", "publishedAt": "2023-07-12 09:00", "category": "local", "description": "Grand opening of our new state-of-the-art community center this weekend.", "communityId": community_id},
            {"title": "Local Artist Wins National Award", "image": "/artist_award.png", "author": "Arts Committee", "publishedAt": "2023-07-11 14:30", "category": "culture", "description": "Lisbon-based painter Maria Santos receives prestigious national art award.", "communityId": community_id},
            {"title": "Beach Cleanup Initiative Launched", "image": "/beach_cleanup.png", "author": "Environmental Group", "publishedAt": "2023-07-10 11:15", "category": "environment", "description": "New program aims to keep our beaches clean with weekly volunteer events.", "communityId": community_id},
            {"title": "Local Restaurant Week Announced", "image": "/restaurant_week.png", "author": "Tourism Board", "publishedAt": "2023-07-09 16:45", "category": "food", "description": "Annual event showcasing the best of Lisbon's culinary scene starts next month.", "communityId": community_id},
        ]

        if not self.item.search(community_id):
            for item in items:
                self.create_item(None, **item)

        if not self.service.search(community_id):
            for service in services:
                self.create_service(None, **service)

        if not self.event.search(community_id):
            for event in events:
                self.create_event(None, **event)

        if not self.news.search(community_id):
            for news_item in news:
                self.create_news(None, **news_item)

    def get_community_by_chat_id(self, chatId):
        return self.community.get_by_chat_id(chatId)

    def create_community(self, chatId, name):
        return self.community.create(chatId, name)

    def create_item(self, id, title, price, image, author, publishedAt, category, description, communityId):
        return self.item.create(id, title, price, image, author, publishedAt, category, description, communityId)

    def search_items(self, communityId):
        return self.item.search(communityId)

    def create_service(self, id, title, price, image, author, publishedAt, category, description, communityId):
        return self.service.create(id, title, price, image, author, publishedAt, category, description, communityId)

    def search_services(self, communityId):
        return self.service.search(communityId)

    def create_event(self, id, title, date, image, author, publishedAt, category, description, communityId):
        return self.event.create(id, title, date, image, author, publishedAt, category, description, communityId)

    def search_events(self, communityId):
        return self.event.search(communityId)

    def create_news(self, id, title, image, author, publishedAt, category, description, communityId):
        return self.news.create(id, title, image, author, publishedAt, category, description, communityId)

    def search_news(self, communityId):
        return self.news.search(communityId)
