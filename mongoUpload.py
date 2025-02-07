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
    try:
        buckets = storage.list_buckets()
        for bucket in buckets['buckets']:
            if bucket['name'] == BUCKET_NAME:
                return bucket['$id']
        
        bucket = storage.create_bucket(
            bucket_id=ID.unique(),
            name=BUCKET_NAME,
            permissions=['read("any")', 'write("any")']
        )
        return bucket['$id']
    except AppwriteException as e:
        print(f"Bucket error: {str(e)}")
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

def upload_image(file):
    try:
        bucket_id = get_or_create_bucket()
        if not bucket_id:
            raise Exception("Failed to get or create bucket")
        
        file = storage.create_file(
            bucket_id=bucket_id,
            file_id=ID.unique(),
            file=InputFile.from_path(file),
            permissions=['read("any")']
        )
        
        file_url = f"https://cloud.appwrite.io/v1/storage/buckets/{bucket_id}/files/{file['$id']}/view?project={PROJECT_ID}&mode=admin"
        print(f"Image URL: {file_url}")
        return file_url
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

if __name__ == "__main__":
    #file = 'temp/downloads/Screenshot_2024-11-12_at_9.51.41_PM.png'
    #upload_image(file)
    files = get_files()
    print("All file URLs:")
    