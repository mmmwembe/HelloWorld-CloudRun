import os
import json
from google.cloud import storage
from dotenv import load_dotenv
import pandas as pd

class GCPOps:
    def __init__(self):
        # Load environment variables from .env file
        load_dotenv()
        
        # Get the Google service account JSON from environment variable
        self.secret_json = os.getenv('GOOGLE_SECRET_JSON')
        self.storage_client = storage.Client.from_service_account_info(
            json.loads(self.secret_json)
        )

    def save_file_to_bucket(self, artifact_url, session_id, bucket_name, subdir="papers", 
                          subsubdirs=["pdf","word","images","csv","text"]):
        """
        Save a file to a GCP bucket with appropriate subdirectory structure.
        """
        # Determine the subsubdir based on the file extension
        if artifact_url.endswith(".docx"):
            subsubdir = "word"
        elif artifact_url.endswith((".jpg", ".jpeg", ".png", ".gif")):
            subsubdir = "images"
        elif artifact_url.endswith(".csv"):
            subsubdir = "csv"
        elif artifact_url.endswith((".txt", ".text")):
            subsubdir = "text"
        else:
            subsubdir = "pdf"  # Default to PDF if no other match

        bucket = self.storage_client.bucket(bucket_name)

        if subsubdir == "word":
            # Delete the contents of the subsubdir before uploading the new file
            blob_prefix = f"{session_id}/{subdir}/{subsubdir}/"
            blobs = self.storage_client.list_blobs(bucket, prefix=blob_prefix)
            for blob in blobs:
                blob.delete()

        try:
            # Upload the file to Google Cloud Storage
            blob_name = f"{session_id}/{subdir}/{subsubdir}/{os.path.basename(artifact_url)}"
            blob = bucket.blob(blob_name)
            blob.upload_from_filename(artifact_url)
            return blob.public_url
        except Exception as e:
            print("An error occurred:", e)
            return None

    def save_tracker_csv(self, df, session_id, bucket_name):
        """
        Save a pandas DataFrame as a CSV to the specified GCS bucket.
        """
        try:
            # Create a temporary local CSV file
            temp_csv_path = os.path.join('static', 'tmp', f'{session_id}.csv')
            os.makedirs(os.path.dirname(temp_csv_path), exist_ok=True)
            
            # Save DataFrame to temporary CSV
            df.to_csv(temp_csv_path, index=False)
            
            # Use save_file_to_bucket to upload the CSV
            url = self.save_file_to_bucket(
                artifact_url=temp_csv_path,
                session_id=session_id,
                bucket_name=bucket_name
            )
            
            # Clean up temporary file
            if os.path.exists(temp_csv_path):
                os.remove(temp_csv_path)
                
            return url
            
        except Exception as e:
            print(f"Error saving tracker CSV: {str(e)}")
            # Clean up temporary file in case of error
            if os.path.exists(temp_csv_path):
                os.remove(temp_csv_path)
            return None

    def initialize_paper_upload_tracker_df_from_gcp(self, session_id, bucket_name):
        """
        Initialize a pandas DataFrame from a CSV file stored in GCS.
        """
        try:
            # Construct the GCS URL
            gcs_url = f"https://storage.googleapis.com/{bucket_name}/{session_id}/papers/csv/{session_id}.csv"
            
            # Read directly from URL
            df = pd.read_csv(gcs_url)
            return df
            
        except Exception as e:
            print(f"Error initializing DataFrame from GCS: {str(e)}")
            # If file doesn't exist or other error, return empty DataFrame with default columns
            return pd.DataFrame(columns=[
                'gcp_public_url',
                'hash',
                'original_filename',
                'citation_name',
                'citation_authors',
                'citation_year',
                'citation_organization',
                'citation_doi',
                'citation_url',
                'upload_timestamp',
                'processed',
            ])

    def get_public_urls(self, bucket_name, session_id, file_hash_num):
        """
        Get public URLs for all files in a specific bucket path.
        """
        bucket = self.storage_client.bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=f"{session_id}/{file_hash_num}/")
        return [f"https://storage.googleapis.com/{bucket_name}/{blob.name}" for blob in blobs]

    def get_public_urls_with_metadata(self, bucket_name, session_id, file_hash_num):
        """
        Get public URLs and metadata for all files in a specific bucket path.
        """
        bucket = self.storage_client.bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=f"{session_id}/{file_hash_num}/")
        
        files = []
        for blob in blobs:
            file_info = {
                'name': blob.name.split('/')[-1],  # File name
                'blob_name': blob.name,  # Full blob name
                'size': f"{blob.size / 1024 / 1024:.2f} MB",  # Size in MB
                'updated': blob.updated.strftime('%Y-%m-%d %H:%M:%S'),  # Last updated timestamp
                'public_url': f"https://storage.googleapis.com/{bucket_name}/{blob.name}"  # Public URL
            }
            files.append(file_info)
        
        return files

    def save_json_to_bucket(self, local_file_path, bucket_name, session_id):
        """
        Save a local JSON file to a GCP bucket.
        """
        try:
            bucket = self.storage_client.bucket(bucket_name)

            # Create the full path in the bucket
            blob_name = f"labels/{session_id}/{session_id}.json"
            blob = bucket.blob(blob_name)

            # Upload the file
            blob.upload_from_filename(local_file_path)

            # Generate the public URL
            public_url = f"https://storage.googleapis.com/{bucket_name}/{blob_name}"

            return public_url
        except Exception as e:
            print(f"Error uploading file to bucket '{bucket_name}': {e}")
            return None

    def load_paper_json_files(self, papers_json_public_url):
        """
        Load existing paper JSON files from GCS.
        """
        try:
            bucket_name = papers_json_public_url.split('/')[3]
            blob_path = '/'.join(papers_json_public_url.split('/')[4:])
            
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            
            if blob.exists():
                content = blob.download_as_string()
                return json.loads(content)
        except Exception as e:
            print(f"Error loading paper JSON files: {str(e)}")
        return []

    def save_paper_json_files(self, papers_json_public_url, paper_json_files):
        """
        Save paper JSON files to GCS.
        """
        try:
            bucket_name = papers_json_public_url.split('/')[3]
            blob_path = '/'.join(papers_json_public_url.split('/')[4:])
            
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            
            blob.upload_from_string(
                json.dumps(paper_json_files),
                content_type='application/json'
            )
            return papers_json_public_url
        except Exception as e:
            print(f"Error saving paper JSON files: {str(e)}")
            return ""