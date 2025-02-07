import logging
from bson.objectid import ObjectId
from pymongo.errors import PyMongoError
from flask import jsonify

import os
import uuid
from pymongo import MongoClient
from gridfs import GridFS
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB Connection
uri = "mongodb+srv://oppurtunest:hAPV3Tf0QoB0GgiQ@cluster0.mbbgm.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

try:
    client = MongoClient(uri)
    db = client['MACRO-users']
    users_collection = db['users']
    keys_collection = db['encryption_keys']
    posts_collection = db['posts']
    fs = GridFS(db)

    # Create indexes
    users_collection.create_index('username', unique=True)
    users_collection.create_index('email', unique=True)
    keys_collection.create_index('user_id', unique=True)
    posts_collection.create_index([('created_at', -1)])

    logger.info("Connected to MongoDB and indexes created.")

except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {str(e)}")
    raise

def get_user_posts(user_id=None):
    """
    Retrieve all posts for the given user_id from the posts collection.
    If user_id is not provided, retrieve all posts.

    :param user_id: The ID of the user whose posts are to be retrieved (optional)
    :return: A JSON response containing the list of posts
    """
    try:
        query = {"user_id": user_id} if user_id else {}

        # Query the posts collection
        posts = list(posts_collection.find(query).sort("created_at", -1))
        all_posts = []

        for post in posts:
            # Convert ObjectId to string for JSON serialization
            post['_id'] = str(post['_id'])

            # If the post has an associated file in GridFS
            if 'file_id' in post:
                try:
                    # Retrieve the file from GridFS
                    gridfs_file = fs.get(ObjectId(post['file_id']))
                    post['file'] = {
                        "filename": gridfs_file.filename,
                        "content_type": gridfs_file.content_type,
                        "data": gridfs_file.read().decode('utf-8', errors='ignore')  # Decode binary if applicable
                    }
                except Exception as e:
                    logger.error(f"Failed to retrieve file for post {post['_id']}: {str(e)}")
                    post['file_error'] = "Failed to retrieve file."

            all_posts.append(post)
            print(all_posts)

        if user_id:
            logger.info(f"Retrieved {len(all_posts)} posts for user_id: {user_id}")
        else:
            logger.info(f"Retrieved {len(all_posts)} posts for all users.")

        return jsonify({"posts": all_posts}), 200

    except PyMongoError as e:
        logger.error(f"Database error while retrieving posts: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve posts: {str(e)}")
        raise

# Example usage
if __name__ == "__main__":
    # Replace with the actual user ID or leave as None to retrieve all posts
    user_id = None  # or "877498dd-5bc1-4a04-9c81-f2004639b288"

    try:
        response = get_user_posts(user_id)
        print(response.get_json())
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
