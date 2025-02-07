# setup.py
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.id import ID
from appwrite.exception import AppwriteException
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_or_create_database(databases, database_id='676da5390025eeffa739', database_name='MACRO Database'):
    try:
        database = databases.get(database_id)
        logger.info(f"Using existing database with ID: {database_id}")
        return database_id
    except AppwriteException as e:
        if 'Database with the requested ID could not be found' in str(e):
            logger.info("Database not found. Creating new database...")
            try:
                database = databases.create(
                    database_id=database_id,
                    name=database_name
                )
                logger.info(f"Created new database with ID: {database['$id']}")
                return database['$id']
            except AppwriteException as create_error:
                logger.error(f"Failed to create database: {str(create_error)}")
                raise
        else:
            logger.error(f"Error checking database: {str(e)}")
            raise

def setup_appwrite():
    client = Client()
    client.set_endpoint('https://cloud.appwrite.io/v1')
    client.set_project('676da1890031e065fd98')
    client.set_key('standard_06bfc36e517c20846d9457968a6afcf30cb6a1a4dd8f1c74139d086c63c0094aefb4b684449f97de498bb1c219110d4f1704c8cb7d0cf5261d5aaf2363a39592eaaa0f7e5063b20c8b6615b5a77b0c9c55dd94957c5e67cfdba9014581f0b26ba07413caf8c8291f6dc5dab5b21dce221e65b39d749c9fbf78066f7f9fbdbddd')
    
    databases = Databases(client)
    
    try:
        database_id = get_or_create_database(databases)
        
        # Users Collection
        try:
            databases.get_collection(database_id, 'users')
            logger.info("Users collection already exists")
        except AppwriteException:
            logger.info("Creating Users Collection...")
            users_collection = databases.create_collection(
                database_id=database_id,
                collection_id='users',
                name='Users Collection',
            )
            
            # Add attributes to Users Collection
            databases.create_string_attribute(
                database_id=database_id,
                collection_id='users',
                key='username',
                size=256,
                required=True,
            )
            time.sleep(1)
            
            databases.create_string_attribute(
                database_id=database_id,
                collection_id='users',
                key='password',  # Added password field
                size=1024,  # Increased size for encrypted password
                required=True,
            )
            time.sleep(1)
            
            databases.create_string_attribute(
                database_id=database_id,
                collection_id='users',
                key='email',
                size=320,
                required=True,
            )
            time.sleep(1)
            
            databases.create_string_attribute(
                database_id=database_id,
                collection_id='users',
                key='role',  # Added role field
                size=256,
                required=True,
            )
            time.sleep(1)
            
            databases.create_string_attribute(
                database_id=database_id,
                collection_id='users',
                key='instrument',  # Added instrument field
                size=256,
                required=False,
            )
            time.sleep(1)
            
            # Create unique index for username
            databases.create_index(
                database_id=database_id,
                collection_id='users',
                key='username_unique',
                type='unique',
                attributes=['username']
            )
            time.sleep(1)
            
            # Create unique index for email
            databases.create_index(
                database_id=database_id,
                collection_id='users',
                key='email_unique',
                type='unique',
                attributes=['email']
            )
            time.sleep(1)
            
            databases.create_datetime_attribute(
                database_id=database_id,
                collection_id='users',
                key='created_at',
                required=True
            )
            logger.info("Users Collection attributes added successfully")

        # Rest of the collections setup remains the same...

        return database_id

    except Exception as e:
        logger.error(f"Error setting up Appwrite schema: {str(e)}")
        raise

# Now let's update the login route in app.py to properly handle the password field

