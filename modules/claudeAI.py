from anthropic import Anthropic
from google.cloud import storage
from datetime import datetime, timedelta
import json
import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class ClaudeAI:
    def __init__(self):
        self.CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')
        self.secret_json = os.getenv('GOOGLE_SECRET_JSON')
        self.client = Anthropic(api_key=self.CLAUDE_API_KEY)
        self.MODEL_NAME = "claude-3-5-sonnet-20241022"

    def get_storage_client(self):
        """Get authenticated GCS client"""
        return storage.Client.from_service_account_info(json.loads(self.secret_json))

    def get_completion(self, messages):
        """
        Sends the request to Claude API and returns the completion.

        Args:
            messages (list): Array of message objects

        Returns:
            str: Claude's response containing the JSON data
        """
        try:
            response = self.client.messages.create(
                model=self.MODEL_NAME,
                max_tokens=8092,
                messages=messages
            )

            try:
                json_response = json.loads(response.content[0].text)
                return json.dumps(json_response, indent=2)
            except json.JSONDecodeError:
                return json.dumps({"error": "Invalid JSON in response"})
            except (IndexError, AttributeError):
                return json.dumps({"error": "Unexpected response format"})

        except Exception as e:
            return json.dumps({"error": str(e)})

    def load_paper_json_files(self, papers_json_public_url):
        """Load existing paper JSON files if they exist."""
        try:
            storage_client = self.get_storage_client()
            bucket_name = papers_json_public_url.split('/')[3]
            blob_path = '/'.join(papers_json_public_url.split('/')[4:])

            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)

            if blob.exists():
                content = blob.download_as_string()
                return json.loads(content)
        except Exception as e:
            print(f"Error loading paper JSON files: {str(e)}")
        return []

    def save_paper_json_files(self, papers_json_public_url, paper_json_files):
        """Save paper JSON files to GCS."""
        try:
            storage_client = self.get_storage_client()
            bucket_name = papers_json_public_url.split('/')[3]
            blob_path = '/'.join(papers_json_public_url.split('/')[4:])

            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)

            blob.upload_from_string(
                json.dumps(paper_json_files),
                content_type='application/json'
            )
            return papers_json_public_url
        except Exception as e:
            print(f"Error saving paper JSON files: {str(e)}")
            return ""

    def load_PAPER_JSON_FILES(self, json_url):
        """Loads and returns paper JSON data from URL"""
        try:
            response = requests.get(json_url)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to load JSON. Status code: {response.status_code}")
                return []
        except Exception as e:
            print(f"Error loading JSON: {str(e)}")
            return []

    def get_DIATOMS_DATA(self, json_url):
        """Load JSON data from URL and extract diatoms_data into an array."""
        DIATOMS_DATA_ARRAY = []
        
        try:
            response = requests.get(json_url)
            response.raise_for_status()
            paper_json_files = response.json()
            
            for paper in paper_json_files:
                diatoms_data = paper.get("diatoms_data")
                
                if diatoms_data:
                    if isinstance(diatoms_data, str):
                        try:
                            diatoms_data = json.loads(diatoms_data)
                        except json.JSONDecodeError:
                            print(f"Skipping invalid JSON in diatoms_data")
                            continue
                    
                    DIATOMS_DATA_ARRAY.append(diatoms_data)
            
            print(f"Successfully extracted diatoms data from {len(DIATOMS_DATA_ARRAY)} papers")
            return DIATOMS_DATA_ARRAY
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from URL: {str(e)}")
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON data: {str(e)}")
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
        
        return []

    def update_and_save_papers(self, json_url, PAPER_JSON_FILES, DIATOMS_DATA):
        """Update papers JSON with modified DIATOMS_DATA and save back to GCS."""
        try:
            diatoms_data_map = {data['image_url']: data for data in DIATOMS_DATA}
            
            for paper in PAPER_JSON_FILES:
                paper_image_urls = paper.get("result", {}).get("paper_image_urls", [])
                
                for image_url in paper_image_urls:
                    if image_url in diatoms_data_map:
                        paper["diatoms_data"] = diatoms_data_map[image_url]
                        break
            
            storage_client = self.get_storage_client()
            bucket_name = json_url.split('/')[3]
            blob_path = '/'.join(json_url.split('/')[4:])
            
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            
            json_content = json.dumps(PAPER_JSON_FILES, indent=2)
            
            blob.upload_from_string(
                json_content,
                content_type='application/json'
            )
            
            print(f"Successfully updated and saved papers JSON to: {json_url}")
            return True
            
        except Exception as e:
            print(f"Error updating and saving papers: {str(e)}")
            return False
        
        
    def get_public_urls(self, bucket_name, session_id):
        try:
            # Get the storage client
            client = self.get_storage_client()

            # Access the specified bucket
            bucket = client.bucket(bucket_name)

            # List all blobs (files) under the specified prefix (pdf/session_id/)
            blobs = bucket.list_blobs(prefix=f"pdf/{session_id}/")

            # Generate the public URLs for the blobs
            return [f"https://storage.googleapis.com/{bucket_name}/{blob.name}" for blob in blobs]
        
        except Exception as e:
            # Log the exception if needed
            print(f"Error retrieving public URLs: {e}")
            # Return an empty list in case of an error
            return []