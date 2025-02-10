from flask import Flask, request, jsonify, render_template, session, redirect, url_for, send_file
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from bson import json_util, ObjectId
from werkzeug.utils import secure_filename
import json
import hashlib
import os
import io
from cryptography.fernet import Fernet
from datetime import datetime, timedelta
import uuid
import logging
from functools import wraps
from gridfs import GridFS
import mimetypes
import tempfile
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.permanent_session_lifetime = timedelta(days=1)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# MongoDB configuration
uri = "mongodb+srv://oppurtunest:hAPV3Tf0QoB0GgiQ@cluster0.mbbgm.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
try:
    client = MongoClient(uri)
    db = client['LOL-users']
    users_collection = db['users']
    keys_collection = db['encryption_keys']
    posts_collection = db['posts']
    comments_collection = db['comments']
    fs = GridFS(db)

    # Create indexes
    users_collection.create_index('username', unique=True)
    users_collection.create_index('email', unique=True)
    keys_collection.create_index('user_id', unique=True)
    posts_collection.create_index([('created_at', -1)])
    comments_collection.create_index([('post_id', 1), ('created_at', -1)])
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {str(e)}")
    raise

# Security helper functions
def generate_key():
    return Fernet.generate_key()

def get_fernet(key):
    return Fernet(key)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def encrypt_data(data, fernet):
    try:
        return fernet.encrypt(data.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption error: {str(e)}")
        raise

def decrypt_data(encrypted_data, fernet):
    try:
        return fernet.decrypt(encrypted_data.encode()).decode()
    except Exception as e:
        logger.error(f"Decryption error: {str(e)}")
        raise

# File handling utilities
def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_file_extension(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

def store_file_in_gridfs(file_data, filename, content_type):
    try:
        if not file_data:
            raise ValueError("Empty file data")
            
        file_id = fs.put(
            io.BytesIO(file_data),
            filename=secure_filename(filename),
            content_type=content_type or 'application/octet-stream'
        )
        # Verify file was stored
        stored_file = fs.get(file_id)
        if not stored_file:
            raise Exception("File not stored properly")
        return str(file_id)
    except Exception as e:
        logger.error(f"Error storing file in GridFS: {str(e)}")
        raise

def get_file_from_gridfs(file_id):
    try:
        file_data = fs.get(ObjectId(file_id))
        if not file_data:
            raise ValueError("File not found")
        return file_data
    except Exception as e:
        logger.error(f"Error retrieving file from GridFS: {str(e)}")
        raise

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# Custom JSON encoder for MongoDB objects
def mongo_json_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    return json_util.default(obj)

# Main routes
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        all_users = list(users_collection.find(
            {},
            {'username': 1, 'user_id': 1, 'role': 1, 'instrument': 1, '_id': 0}
        ))

        user_list = []
        for user in all_users:
            key_doc = keys_collection.find_one({"user_id": user['user_id']})
            if key_doc:
                fernet = get_fernet(key_doc['key'])
                user_info = {
                    'username': user['username'],
                    'role': decrypt_data(user['role'], fernet)
                }
                if 'instrument' in user:
                    user_info['instrument'] = decrypt_data(user['instrument'], fernet)
                user_list.append(user_info)

        return render_template('dashboard.html', users=user_list)
    except Exception as e:
        logger.error(f"Error fetching user list: {str(e)}")
        return render_template('dashboard.html', users=[])

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({
        "status": "success",
        "message": "Pong!",
        "timestamp": datetime.utcnow().isoformat()
    }), 200
# Authentication routes
@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({"error": "Missing required fields"}), 400

        user = users_collection.find_one({"username": username})
        if not user:
            return jsonify({"error": "Invalid credentials"}), 401

        key_doc = keys_collection.find_one({"user_id": user['user_id']})
        if not key_doc:
            return jsonify({"error": "Invalid credentials"}), 401

        fernet = get_fernet(key_doc['key'])
        decrypted_password = decrypt_data(user['password'], fernet)
        decrypted_role = decrypt_data(user['role'], fernet)

        if decrypted_password != hash_password(password):
            return jsonify({"error": "Invalid credentials"}), 401

        session.permanent = True
        session['user_id'] = user['user_id']
        session['username'] = user['username']
        session['role'] = decrypted_role

        logger.info(f"User logged in: {username}")
        return jsonify({
            "message": "Login successful",
            "redirect": url_for('dashboard')
        }), 200

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({"error": "An error occurred during login"}), 500
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')

    try:
        # Retrieve form data
        print(request.form)
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        dob = request.form.get('dob')
        gender = request.form.get('gender', '')
        interested_in = request.form.get('interested-in', '')
        location = request.form.get('location', '')
        meme_genre = request.form.get('meme-genre', '')
        meme_style = request.form.get('meme-style', '')
        meme_template = request.form.get('meme-template', '')

        # Validate required fields
        print([username, email, password, dob])
        if not all([username, email, password, dob]):
            return jsonify({"error": "Missing required fields"}), 400

        # Validate date of birth
        try:
            birth_date = datetime.strptime(dob, '%Y-%m-%d')
            age = datetime.now().year - birth_date.year
            if age < 18:
                return jsonify({"error": "You must be at least 18 years old"}), 400
        except ValueError:
            return jsonify({"error": "Invalid date format"}), 400

        # File handling
        profile_picture = request.files.get('profile-picture')
        meme_upload = request.files.get('meme-upload')

        # Generate encryption
        user_id = str(uuid.uuid4())
        encryption_key = generate_key()
        fernet = get_fernet(encryption_key)

        # Prepare user data
        user = {
            "user_id": user_id,
            "username": username,
            "email": encrypt_data(email, fernet),
            "password": encrypt_data(hash_password(password), fernet),
            "role": encrypt_data("User", fernet),
            "dob": birth_date,
            "gender": encrypt_data(gender, fernet) if gender else None,
            "interested_in": encrypt_data(interested_in, fernet) if interested_in else None,
            "location": encrypt_data(location, fernet) if location else None,
            "meme_preferences": {
                "genre": encrypt_data(meme_genre, fernet) if meme_genre else None,
                "style": encrypt_data(meme_style, fernet) if meme_style else None,
                "template": encrypt_data(meme_template, fernet) if meme_template else None
            },
            "created_at": datetime.utcnow()
        }

        # Handle profile picture upload
        if profile_picture:
            profile_pic_result = upload_image(profile_picture)
            if profile_pic_result:
                user['profile_picture_url'] = profile_pic_result['file_url']

        # Handle meme upload
        if meme_upload:
            meme_result = upload_image(meme_upload)
            if meme_result:
                user['favorite_meme_url'] = meme_result['file_url']

        # Prepare encryption key document
        key_doc = {
            "user_id": user_id,
            "key": encryption_key
        }

        # Insert user and key documents
        users_collection.insert_one(user)
        keys_collection.insert_one(key_doc)

        # Set up session for the new user
        session.permanent = True
        session['user_id'] = user_id
        session['username'] = username
        session['role'] = "User"  # Default role for new users

        logger.info(f"New user registered: {username}")
        return jsonify({"message": "Signup successful", "redirect": url_for('dashboard')}), 201

    except DuplicateKeyError:
        return jsonify({"error": "Username or email already exists"}), 400
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        return jsonify({"error": "An error occurred during signup"}), 500


@app.route('/logout')
def logout():
    username = session.get('username')
    session.clear()
    if username:
        logger.info(f"User logged out: {username}")
    return jsonify({"message": "Logged out successfully"}), 200

from appwrite.client import Client
from appwrite.services.storage import Storage
from appwrite.input_file import InputFile
from appwrite.id import ID
from appwrite.exception import AppwriteException

client = Client()
client.set_endpoint('https://cloud.appwrite.io/v1')
client.set_project('676da1890031e065fd98')
client.set_key('standard_06bfc36e517c20846d9457968a6afcf30cb6a1a4dd8f1c74139d086c63c0094aefb4b684449f97de498bb1c219110d4f1704c8cb7d0cf5261d5aaf2363a39592eaaa0f7e5063b20c8b6615b5a77b0c9c55dd94957c5e67cfdba9014581f0b26ba07413caf8c8291f6dc5dab5b21dce221e65b39d749c9fbf78066f7f9fbdbddd')
storage = Storage(client)
PROJECT_ID = '676da1890031e065fd98'
BUCKET_NAME = 'MACRO-Posts Bucket'

def get_or_create_bucket():
    """
    Get existing bucket or create new one in Appwrite.
    
    Returns:
        str: Bucket ID if successful, None if failed
    """
    try:
        # List all buckets and check if ours exists
        buckets = storage.list_buckets()
        for bucket in buckets['buckets']:
            if bucket['name'] == BUCKET_NAME:
                logger.info(f"Found existing bucket: {bucket['$id']}")
                return bucket['$id']
        
        # Create new bucket if not found
        bucket = storage.create_bucket(
            bucket_id=ID.unique(),
            name=BUCKET_NAME,
            permissions=['read("any")', 'write("any")'],
            file_security=False,  # Allow public access to files
            maximum_file_size=30_000_000  # 30MB limit
        )
        logger.info(f"Created new bucket: {bucket['$id']}")
        return bucket['$id']
        
    except AppwriteException as e:
        logger.error(f"Appwrite bucket error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_or_create_bucket: {str(e)}")
        return None

def upload_image(file):
    """
    Upload a file to Appwrite storage.
    
    Args:
        file: FileStorage object from Flask request.files
        
    Returns:
        dict: Contains file_id and file_url if successful, None if failed
    """
    try:
        bucket_id = get_or_create_bucket()
        if not bucket_id:
            raise Exception("Failed to get or create bucket")
        
        # Ensure filename is secure
        filename = secure_filename(file.filename)
        
        # Create a temporary file with proper extension
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
            file.save(temp_file.name)
            
            # Generate a unique file ID
            file_id = ID.unique()
            
            # Upload to Appwrite
            file_upload = storage.create_file(
                bucket_id=bucket_id,
                file_id=file_id,
                file=InputFile.from_path(temp_file.name),
                permissions=['read("any")']
            )
            
            # Clean up temporary file
            os.unlink(temp_file.name)
        
        # Generate public URL for the file
        file_url = f"https://cloud.appwrite.io/v1/storage/buckets/{bucket_id}/files/{file_upload['$id']}/view?project={PROJECT_ID}&mode=admin"
        
        logger.info(f"File uploaded successfully: {file_id}")
        return {
            "file_id": file_upload['$id'],
            "file_url": file_url
        }
        
    except AppwriteException as e:
        logger.error(f"Appwrite upload error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in upload_image: {str(e)}")
        return None

def get_files():
    try:
        bucket_id = get_or_create_bucket()
        if not bucket_id:
            raise Exception("Failed to get bucket")
            
        files = storage.list_files(bucket_id)
        file_urls = []
        for file in files['files']:
            url = f"https://cloud.appwrite.io/v1/storage/buckets/{bucket_id}/files/{file['$id']}/view?project={PROJECT_ID}&mode=admin"
            file_urls.append(url)
        return file_urls
    except Exception as e:
        print(f"Error getting files: {str(e)}")
        return []


def upload_file(file_path, session, post_type, content=None):
    """
    Upload an image or audio file to MongoDB and store its metadata in the posts collection.

    :param file_path: Path to the file to upload
    :param session: Session dictionary containing 'user_id' and 'username'
    :param post_type: Type of the post (e.g., 'image', 'audio', 'text', etc.)
    :param content: Additional content or text related to the post
    """
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Ensure session contains required fields
        if 'user_id' not in session or 'username' not in session:
            raise ValueError("Session must contain 'user_id' and 'username'.")

        file_id = None
        file_name = upload_image(file_path)
        
        # Read the file content and upload it to GridFS if file_path is provided
        with open(file_path, 'rb') as file_data:
            file_id = fs.put(file_data, filename=file_name, content_type=post_type)
        
        # Prepare the post metadata
        post_metadata = {
            "post_id": str(uuid.uuid4()),
            "user_id": session['user_id'],
            "username": session['username'],
            "type": post_type,
            "content": content if content else "",
            "file_id": str(file_id) if file_id else None,
            "created_at": datetime.utcnow(),
            "likes": 0,
            "comments": []
        }
        
        # Insert metadata into the posts collection
        posts_collection.insert_one(post_metadata)
        logger.info(f"Post created successfully. Post ID: {post_metadata['post_id']}")
        return post_metadata
    
    except Exception as e:
        logger.error(f"Failed to upload file and create post: {str(e)}")
        raise
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    return app.send_static_file('index.html')
# Posts routes
@app.route('/posts', methods=['GET', 'POST'])
@login_required
def handle_posts():
    if request.method == 'GET':
        try:
            # Get the last update timestamp if provided
            last_update = request.args.get('last_update', None)
            query = {}
            
            if last_update:
                query['created_at'] = {'$gt': datetime.fromisoformat(last_update)}
            
            # Query posts collection with specific field projection
            posts = list(posts_collection.find(
                query,
                {
                    '_id': 0,
                    'username': 1,
                    'created_at': 1,
                    'file_url': 1,  # URL of the file from Appwrite
                    'likes': 1,
                    'comment_count': 1,
                    'content': 1,  # Including content in case it's needed
                    'type': 1      # Including type to differentiate between image/audio
                }
            ).sort('created_at', -1).limit(50))

            # Format the timestamp for each post
            formatted_posts = []
            for post in posts:
                formatted_post = {
                    'username': post['username'],
                    'time': post['created_at'].isoformat(),
                    'file_url': post.get('file_url', ''),
                    'likes': post.get('likes', 0),
                    'comments': post.get('comment_count', 0),
                    'content': post.get('content', ''),
                    'type': post.get('type', '')
                }
                formatted_posts.append(formatted_post)

            return jsonify({
                'posts': formatted_posts,
                'last_update': datetime.now().isoformat()
            }), 200

        except Exception as e:
            logger.error(f"Error fetching posts: {str(e)}")
            return jsonify({"error": "An error occurred fetching posts"}), 500

    elif request.method == 'POST':
        try:
            # Validate request data
            post_type = request.form.get('type')
            content = request.form.get('content', '')
            file = request.files.get('post-file')

            if not file:
                return jsonify({"error": "No file provided"}), 400
            if not post_type:
                return jsonify({"error": "Post type is required"}), 400

            # Check file type
            allowed_image_types = {'image/jpeg', 'image/png', 'image/gif'}
            allowed_audio_types = {'audio/mpeg', 'audio/wav', 'audio/mp3'}
            file_type = file.content_type

            if post_type == 'image' and file_type not in allowed_image_types:
                return jsonify({"error": "Invalid image format"}), 400
            elif post_type == 'audio' and file_type not in allowed_audio_types:
                return jsonify({"error": "Invalid audio format"}), 400

            # Upload file to Appwrite
            upload_result = upload_image(file)
            if not upload_result:
                return jsonify({"error": "Failed to upload file"}), 500

            # Create post in MongoDB
            post_data = {
                "post_id": str(uuid.uuid4()),
                "user_id": session['user_id'],
                "username": session['username'],
                "type": post_type,
                "content": content,
                "file_url": upload_result['file_url'],
                "file_id": upload_result['file_id'],
                "created_at": datetime.utcnow(),
                "likes": 0,
                "likes_by": [],
                "comment_count": 0
            }

            result = posts_collection.insert_one(post_data)
            if not result.inserted_id:
                # If MongoDB insert fails, attempt to delete the uploaded file
                try:
                    delete_file_from_appwrite(upload_result['file_id'])
                except Exception as e:
                    logger.error(f"Failed to cleanup Appwrite file after MongoDB error: {str(e)}")
                return jsonify({"error": "Failed to create post"}), 500

            post_data.pop('_id', None)
            logger.info(f"Post created successfully by {session['username']}")
            return json.loads(json.dumps(post_data, default=mongo_json_serializer)), 201

        except Exception as e:
            logger.error(f"Error creating post: {str(e)}")
            return jsonify({"error": "An error occurred creating post"}), 500


@app.route('/files/<file_id>')
def serve_file(file_id):
    try:
        file_data = get_file_from_gridfs(file_id)
        return send_file(
            io.BytesIO(file_data.read()),
            mimetype=file_data.content_type,
            as_attachment=True,
            download_name=file_data.filename
        )
    except Exception as e:
        logger.error(f"Error serving file: {str(e)}")
        return jsonify({"error": "File not found"}), 404

@app.route('/posts/audio')
@login_required
def get_audio_posts():
    try:
        audio_posts = list(posts_collection.find(
            {"type": "audio"},
            {'_id': 0}
        ).sort('created_at', -1))
        
        return json.loads(json.dumps(audio_posts, default=mongo_json_serializer)), 200
    except Exception as e:
        logger.error(f"Error fetching audio posts: {str(e)}")
        return jsonify({"error": "An error occurred fetching audio posts"}), 500

@app.route('/posts/<post_id>', methods=['DELETE', 'PUT'])
@login_required
def manage_post(post_id):
    if request.method == 'DELETE':
        try:
            post = posts_collection.find_one({"post_id": post_id})
            
            if not post:
                return jsonify({"error": "Post not found"}), 404
                
            if post['user_id'] != session['user_id']:
                return jsonify({"error": "Unauthorized"}), 403
            
            if 'file_id' in post and post['file_id']:
                try:
                    fs.delete(ObjectId(post['file_id']))
                except Exception as e:
                    logger.error(f"Error deleting file: {str(e)}")
                
            result = posts_collection.delete_one({"post_id": post_id})
            
            if result.deleted_count == 0:
                return jsonify({"error": "Failed to delete post"}), 500
                
            logger.info(f"Post {post_id} deleted by user {session['username']}")
            return jsonify({"message": "Post deleted successfully"}), 200
            
        except Exception as e:
            logger.error(f"Error deleting post: {str(e)}")
            return jsonify({"error": "An error occurred deleting post"}), 500

    elif request.method == 'PUT':
        try:
            post = posts_collection.find_one({"post_id": post_id})
            
            if not post:
                return jsonify({"error": "Post not found"}), 404
                
            if post['user_id'] != session['user_id']:
                return jsonify({"error": "Unauthorized"}), 403

            data = request.json
            updated_content = data.get('content')
            
            if not updated_content:
                return jsonify({"error": "Content is required"}), 400

            result = posts_collection.update_one(
                {"post_id": post_id},
                {"$set": {"content": updated_content, "updated_at": datetime.utcnow()}}
            )

            if result.modified_count == 0:
                return jsonify({"error": "Failed to update post"}), 500

            return jsonify({"message": "Post updated successfully"}), 200

        except Exception as e:
            logger.error(f"Error updating post: {str(e)}")
            return jsonify({"error": "An error occurred updating post"})

@app.route('/posts/<post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    try:
        post = posts_collection.find_one({"post_id": post_id})
        
        if not post:
            return jsonify({"error": "Post not found"}), 404

        # Check if user has already liked the post
        if 'likes_by' not in post:
            post['likes_by'] = []

        user_id = session['user_id']
        
        if user_id in post['likes_by']:
            # Unlike the post
            result = posts_collection.update_one(
                {"post_id": post_id},
                {
                    "$pull": {"likes_by": user_id},
                    "$inc": {"likes": -1}
                }
            )
            action = "unliked"
        else:
            # Like the post
            result = posts_collection.update_one(
                {"post_id": post_id},
                {
                    "$push": {"likes_by": user_id},
                    "$inc": {"likes": 1}
                }
            )
            action = "liked"

        if result.modified_count == 0:
            return jsonify({"error": "Failed to update post"}), 500

        return jsonify({
            "message": f"Post {action} successfully",
            "likes": post['likes'] + (1 if action == "liked" else -1)
        }), 200

    except Exception as e:
        logger.error(f"Error handling post like: {str(e)}")
        return jsonify({"error": "An error occurred processing like"}), 500

@app.route('/posts/<post_id>/comments', methods=['GET', 'POST'])
@login_required
def handle_comments(post_id):
    if request.method == 'GET':
        try:
            comments = list(comments_collection.find(
                {"post_id": post_id},
                {'_id': 0}
            ).sort('created_at', -1))
            
            return json.loads(json.dumps(comments, default=mongo_json_serializer)), 200
        
        except Exception as e:
            logger.error(f"Error fetching comments: {str(e)}")
            return jsonify({"error": "An error occurred fetching comments"}), 500

    elif request.method == 'POST':
        try:
            data = request.json
            content = data.get('content')

            if not content:
                return jsonify({"error": "Comment content is required"}), 400

            comment = {
                "comment_id": str(uuid.uuid4()),
                "post_id": post_id,
                "user_id": session['user_id'],
                "username": session['username'],
                "content": content,
                "created_at": datetime.utcnow()
            }

            result = comments_collection.insert_one(comment)
            
            # Update post with comment count
            posts_collection.update_one(
                {"post_id": post_id},
                {"$inc": {"comment_count": 1}}
            )
            
            comment.pop('_id', None)
            return json.loads(json.dumps(comment, default=mongo_json_serializer)), 201

        except Exception as e:
            logger.error(f"Error creating comment: {str(e)}")
            return jsonify({"error": "An error occurred creating comment"}), 500

@app.route('/posts/<post_id>/comments/<comment_id>', methods=['PUT', 'DELETE'])
@login_required
def manage_comment(post_id, comment_id):
    if request.method == 'PUT':
        try:
            comment = comments_collection.find_one({
                "comment_id": comment_id,
                "post_id": post_id
            })
            
            if not comment:
                return jsonify({"error": "Comment not found"}), 404
                
            if comment['user_id'] != session['user_id']:
                return jsonify({"error": "Unauthorized"}), 403

            data = request.json
            updated_content = data.get('content')
            
            if not updated_content:
                return jsonify({"error": "Content is required"}), 400

            result = comments_collection.update_one(
                {"comment_id": comment_id},
                {
                    "$set": {
                        "content": updated_content,
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            if result.modified_count == 0:
                return jsonify({"error": "Failed to update comment"}), 500

            return jsonify({"message": "Comment updated successfully"}), 200

        except Exception as e:
            logger.error(f"Error updating comment: {str(e)}")
            return jsonify({"error": "An error occurred updating comment"}), 500

    elif request.method == 'DELETE':
        try:
            comment = comments_collection.find_one({
                "comment_id": comment_id,
                "post_id": post_id
            })
            
            if not comment:
                return jsonify({"error": "Comment not found"}), 404
                
            if comment['user_id'] != session['user_id']:
                return jsonify({"error": "Unauthorized"}), 403

            result = comments_collection.delete_one({"comment_id": comment_id})
            
            if result.deleted_count == 0:
                return jsonify({"error": "Failed to delete comment"}), 500
            
            # Update post with comment count
            posts_collection.update_one(
                {"post_id": post_id},
                {"$inc": {"comment_count": -1}}
            )
                
            return jsonify({"message": "Comment deleted successfully"}), 200

        except Exception as e:
            logger.error(f"Error deleting comment: {str(e)}")
            return jsonify({"error": "An error occurred deleting comment"}), 500

@app.route('/search/users')
@login_required
def search_users():
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify([])
        
    try:
        users = list(users_collection.find({}, {'_id': 0}))
        search_results = []
        
        for user in users:
            key_doc = keys_collection.find_one({"user_id": user['user_id']})
            if key_doc:
                fernet = get_fernet(key_doc['key'])
                decrypted_role = decrypt_data(user['role'], fernet)
                user_info = {
                    "username": user['username'],
                    "role": decrypted_role
                }
                
                if 'instrument' in user:
                    user_info['instrument'] = decrypt_data(user['instrument'], fernet)
                    
                if (query in user['username'].lower() or 
                    query in decrypted_role.lower() or 
                    ('instrument' in user_info and query in user_info['instrument'].lower())):
                    search_results.append(user_info)
                    
        return jsonify(search_results)
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return jsonify({"error": "Search failed"}), 500

@app.route('/user/profile', methods=['GET', 'PUT'])
@login_required
def manage_profile():
    if request.method == 'GET':
        try:
            user = users_collection.find_one({"user_id": session['user_id']})
            if not user:
                return jsonify({"error": "User not found"}), 404

            key_doc = keys_collection.find_one({"user_id": user['user_id']})
            if not key_doc:
                return jsonify({"error": "User data unavailable"}), 500

            fernet = get_fernet(key_doc['key'])

            profile = {
                "username": user['username'],
                "email": decrypt_data(user['email'], fernet),
                "role": decrypt_data(user['role'], fernet)
            }

            if 'instrument' in user:
                profile['instrument'] = decrypt_data(user['instrument'], fernet)

            return jsonify(profile), 200

        except Exception as e:
            logger.error(f"Error fetching user profile: {str(e)}")
            return jsonify({"error": "An error occurred fetching user profile"}), 500

    elif request.method == 'PUT':
        try:
            data = request.json
            user = users_collection.find_one({"user_id": session['user_id']})
            if not user:
                return jsonify({"error": "User not found"}), 404

            key_doc = keys_collection.find_one({"user_id": user['user_id']})
            if not key_doc:
                return jsonify({"error": "User data unavailable"}), 500

            fernet = get_fernet(key_doc['key'])
            update_fields = {}

            # Validate username change
            if 'username' in data and data['username'] != user['username']:
                # Check if username is already taken
                existing_user = users_collection.find_one({"username": data['username']})
                if existing_user and existing_user['user_id'] != session['user_id']:
                    return jsonify({"error": "Username already taken"}), 400
                update_fields['username'] = data['username']

            # Handle password update
            if 'password' in data and data['password']:
                salt = bcrypt.gensalt()
                hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), salt)
                update_fields['password'] = hashed_password

            # Handle email update
            if 'email' in data:
                update_fields['email'] = encrypt_data(data['email'], fernet)

            # Handle role update
            if 'role' in data:
                # Validate role
                valid_roles = ['musician', 'listener', 'producer']
                if data['role'].lower() not in valid_roles:
                    return jsonify({"error": "Invalid role"}), 400
                update_fields['role'] = encrypt_data(data['role'].capitalize(), fernet)
                # Update session role
                session['role'] = data['role'].capitalize()

            # Handle instrument update
            if 'role' in data and data['role'].lower() == 'musician':
                if 'instrument' in data and data['instrument']:
                    update_fields['instrument'] = encrypt_data(data['instrument'], fernet)
            else:
                # If role is not musician, remove instrument if it exists
                update_fields['$unset'] = {'instrument': ''}

            if update_fields:
                if '$unset' in update_fields:
                    unset_operation = {'$unset': update_fields.pop('$unset')}
                    users_collection.update_one(
                        {"user_id": session['user_id']},
                        unset_operation
                    )

                if update_fields:  # If there are still fields to update
                    result = users_collection.update_one(
                        {"user_id": session['user_id']},
                        {"$set": update_fields}
                    )

                    if result.modified_count == 0 and len(update_fields) > 0:
                        return jsonify({"error": "Failed to update profile"}), 500

            return jsonify({"message": "Profile updated successfully"}), 200

        except Exception as e:
            logger.error(f"Error updating user profile: {str(e)}")
            return jsonify({"error": "An error occurred updating user profile"}), 500
@app.template_filter('datetime')
def format_datetime(value, format='%Y-%m-%d %H:%M:%S'):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.strftime(format)

@app.route('/<username>')
def user_profile(username):
    try:
        # Fetch user details
        user_data = users_collection.find_one({"username": username})
        if not user_data:
            return jsonify({"error": "User not found"}), 404

        # Fetch the encryption key
        key_doc = keys_collection.find_one({"user_id": user_data["user_id"]})
        if not key_doc:
            return jsonify({"error": "Encryption key not found"}), 500
        
        fernet = Fernet(key_doc["key"])
        
        # Decrypt sensitive fields
        decrypted_data = {
            "username": user_data["username"],
            "role": fernet.decrypt(user_data["role"].encode()).decode(),
            "instrument": fernet.decrypt(user_data["instrument"].encode()).decode() if "instrument" in user_data else None,
        }
        
        # Fetch user's posts and format them properly
        posts = list(posts_collection.find({"user_id": user_data["user_id"]}).sort("created_at", -1))
        formatted_posts = []
        
        for post in posts:
            formatted_post = {
                "_id": str(post["_id"]),
                "username": post["username"],
                "content": post.get("content", ""),
                "type": post.get("type", ""),
                "file_url": post.get("file_url", ""),
                "likes": post.get("likes", 0),
                "comment_count": post.get("comment_count", 0),
                "created_at": post["created_at"]
            }
            formatted_posts.append(formatted_post)

        # Prepare stats
        stats = {
            "total_posts": len(posts),
            "total_likes": sum(post.get("likes", 0) for post in posts),
            "total_comments": comments_collection.count_documents({"post_id": {"$in": [str(post["_id"]) for post in posts]}})
        }

        return render_template(
            "user_profile.html",
            user=decrypted_data,
            stats=stats,
            posts=formatted_posts,
            recent_activities=[]  # Fetch recent activities if implemented
        )

    except Exception as e:
        logger.error(f"Error loading profile for {username}: {e}")
        return jsonify({"error": "An internal error occurred"}), 500


# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(debug=True)
