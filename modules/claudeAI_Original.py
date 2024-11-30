from anthropic import Anthropic
from google.cloud import storage
import json
import base64
import os
import requests
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')

secret_json = os.getenv('GOOGLE_SECRET_JSON')

# Initialize Claude AI client
client = Anthropic(api_key=CLAUDE_API_KEY)

# Model configuration
MODEL_NAME = "claude-3-5-sonnet-20241022"

def part1_create_paper_info_json_from_pdf_text_content_prompt():
    """
    Creates a structured prompt for Claude to process diatom data.
    Returns a string containing the prompt with instructions and expected JSON structure.
    """
    prompt = """
    Please analyze the provided text and extract information about marine diatoms.
    Return the data in the following JSON structure, maintaining strict adherence to the schema:

    {
        "figure_caption": "Plate 3: Marine Diatoms from the Azores",
        "source_material_location": "South East coast of Faial, Caldeira Inferno",
        "source_material_coordinates": "38° 31' N; 28° 38' W",
        "source_material_description": "An open crater of a small volcano, shallow and sandy. Gathered from Pinna (molluscs) and stones.",
        "source_material_date_collected": "June 1st, 1981",
        "source_material_received_from": "Hans van den Heuvel, Leiden",
        "source_material_date_received": "March 17th, 1988",
        "source_material_note": "Material also deposited in Rijksherbarium Leiden, the Netherlands. Aliquot sample and slide also in collection Sterrenburg, Nr. 249.",
        "diatom_species_array": [
            {
                "species_index": 65,
                "species_name": "Diploneis bombus",
                "species_authors": ["Cleve-Euler", "Backman"],
                "species_year": 1922,
                "species_references": [
                    {
                        "author": "Hendey",
                        "year": 1964,
                        "figure": "pl. 32, fig. 2"
                    },
                    Repeat as necessary
                ],
                "formatted_species_name": "Diploneis_bombus",
                "genus": "Diploneis",
                "species_magnification": "1000",
                "species_scale_bar_microns": "30",
                "species_note": ""
            },
            Repeat as necessary
        ]
    }

    Important instructions:
    1. Extract all information exactly as presented in the source text
    2. Maintain proper formatting for scientific names
    3. Ensure all dates are in the original format
    4. Convert coordinates to standardized format (degrees, minutes)
    5. Include all references with complete citation information
    6. Generate formatted_species_name by replacing spaces with underscores
    7. Leave empty strings for missing information rather than omitting fields
    8. Ensure all numerical values are properly typed (numbers not strings)

    Parse the provided text and return only the JSON object without any additional text or explanation.
    """
    return prompt

def part1_create_messages_for_paper_info_json(pdf_text_content, prompt):
    """
    Creates the message array for the Claude API request.

    Args:
        pdf_text_content (str): The extracted text from the PDF
        prompt (str): The formatted prompt with instructions

    Returns:
        list: Array of message objects for the API request
    """
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": pdf_text_content
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        }
    ]


def part2_create_diatoms_data_object_for_paper():
    """
    Creates a structured prompt for Claude to process diatom data.
    Returns a string containing the prompt with instructions and expected JSON structure.
    """
    prompt = """
    Please analyze the provided paper information and image URLs to extract information about diatoms.
    Return the data in the following JSON structure, maintaining strict adherence to the schema:

    
        {
            "image_url": "get respective full url from paper_image_url for this dict",
            "image_width": "",
            "image_height": "",
            "info": [
                {
                    "label": ["39 Amphora_obtusa_var_oceanica"],
                    "index": 39,
                    "species": "Amphora_obtusa_var_oceanica",
                    "bbox": "",
                    "yolo_bbox": "",
                    "segmentation": "",
                    "embeddings": ""
                }
            ]
        }
   
    Important instructions:
    1. Extract all information exactly as presented in the source text
    2. Use index and formatted_species_name for label and formatted species for species
    3. Leave empty strings for missing information rather than omitting fields
    4. Ensure all JSON fields are properly quoted and formatted

    Parse the provided information and return only the JSON object without any additional text or explanation.
    """
    return prompt

def part2_create_messages_for_diatoms_data_object_creation(paper_info, paper_image_urls, prompt):  # Fixed: Added prompt as third parameter
    """
    Creates the message array for the Claude API request.

    Args:
        paper_info (dict): Dictionary containing paper information and diatom species data
        paper_image_urls (list): List of image URLs associated with the paper
        prompt (str): The formatted prompt with instructions

    Returns:
        list: Array of message objects for the API request
    """
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"Paper Information: {json.dumps(paper_info, indent=2)}"
                },
                {
                    "type": "text",
                    "text": f"Image URLs: {json.dumps(paper_image_urls, indent=2)}"
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        }
    ]


def get_completion(messages):
    """
    Sends the request to Claude API and returns the completion.

    Args:
        messages (list): Array of message objects

    Returns:
        str: Claude's response containing the JSON data
    """
    try:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=8092,
            messages=messages
        )

        # The response.content is already a string, so we can parse it directly
        try:
            # First parse it to validate it's proper JSON
            json_response = json.loads(response.content[0].text)
            # Then format it nicely with indentation
            return json.dumps(json_response, indent=2)
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid JSON in response"})
        except (IndexError, AttributeError):
            return json.dumps({"error": "Unexpected response format"})

    except Exception as e:
        return json.dumps({"error": str(e)})
    

def get_storage_client():
    """Get authenticated GCS client"""
    return storage.Client.from_service_account_info(json.loads(secret_json))

def load_paper_json_files(papers_json_public_url):
    """Load existing paper JSON files if they exist."""
    try:
        storage_client = get_storage_client()
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


def save_paper_json_files(papers_json_public_url, paper_json_files):
    """Save paper JSON files to GCS."""
    try:
        storage_client = get_storage_client()
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

def safe_value(value):
    return value if value else ""    

# Load_PAPER_JSON_FILES function
def load_PAPER_JSON_FILES(json_url):
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
   
# get_DIATOMS_DATA function
def get_DIATOMS_DATA(json_url):
    """
    Load JSON data from URL and extract diatoms_data into an array.
    
    Args:
        json_url (str): URL to the JSON file
        
    Returns:
        list: Array of diatoms_data from all papers
    """
    DIATOMS_DATA_ARRAY = []
    
    try:
        # Fetch and parse JSON data
        response = requests.get(json_url)
        response.raise_for_status()
        paper_json_files = response.json()
        
        # Extract diatoms_data from each paper
        for paper in paper_json_files:
            diatoms_data = paper.get("diatoms_data")
            
            if diatoms_data:
                # Parse if string JSON
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
    

# Update and Save PAPER_JSON_FILES with Updated DIATOMS_DATA
def update_and_save_papers(json_url, PAPER_JSON_FILES, DIATOMS_DATA):
    """
    Update papers JSON with modified DIATOMS_DATA and save back to GCS.
    
    Args:
        json_url (str): URL to the JSON file
        PAPER_JSON_FILES (list): Original papers data
        DIATOMS_DATA (list): Modified diatoms data array
    """
    try:
        # Create a mapping of image_url to diatoms_data for easy lookup
        diatoms_data_map = {data['image_url']: data for data in DIATOMS_DATA}
        
        # Update each paper's diatoms_data
        for paper in PAPER_JSON_FILES:
            # Get relevant image URLs for this paper
            paper_image_urls = paper.get("result", {}).get("paper_image_urls", [])
            
            # Find matching diatoms_data by image_url
            for image_url in paper_image_urls:
                if image_url in diatoms_data_map:
                    paper["diatoms_data"] = diatoms_data_map[image_url]
                    break
        
        # Save updated papers back to GCS
        storage_client = get_storage_client()
        bucket_name = json_url.split('/')[3]
        blob_path = '/'.join(json_url.split('/')[4:])
        
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        # Convert to JSON string with proper formatting
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

# Example usage:
# update_and_save_papers(json_url, PAPER_JSON_FILES, DIATOMS_DATA)
