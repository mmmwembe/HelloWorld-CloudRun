"""
Claude AI Integration Script for Processing Diatom Research Papers

This script provides functionality to interact with the Claude API for processing
scientific papers about diatoms, managing storage in Google Cloud Storage, and
handling various data processing tasks.
"""

from anthropic import Anthropic
from google.cloud import storage
import logging
from typing import List, Dict, Optional, Any, Union, Tuple
from datetime import datetime, timedelta
from dotenv import load_dotenv
import json
import os
import requests

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ClaudeAI:
    """
    A class to handle interactions with Claude AI API and manage paper data storage.
    """
    
    def __init__(self):
        """Initialize the ClaudeAI instance with necessary credentials and configurations."""
        self.CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')
        self.secret_json = os.getenv('GOOGLE_SECRET_JSON')
        self.client = Anthropic(api_key=self.CLAUDE_API_KEY)
        self.MODEL_NAME = "claude-3-5-sonnet-20241022"

    # Core API Methods
    def get_completion(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Send a request to Claude API and return the completion.

        Args:
            messages (list): Array of message objects

        Returns:
            dict: Parsed JSON response from Claude
        """
        try:
            response = self.client.messages.create(
                model=self.MODEL_NAME,
                max_tokens=8092,
                messages=messages
            )

            try:
                return json.loads(response.content[0].text)
            except json.JSONDecodeError:
                return {"error": "Invalid JSON in response"}
            except (IndexError, AttributeError):
                return {"error": "Unexpected response format"}

        except Exception as e:
            return {"error": str(e)}

    def process_paper(self, full_text: str) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        """
        Process a paper's full text to extract paper info, diatoms data, and image URLs.
        
        Args:
            full_text (str): The complete text content of the paper
            
        Returns:
            tuple: (paper_info, paper_diatoms_data, paper_image_urls)
                - paper_info: Dictionary containing paper information
                - paper_diatoms_data: Dictionary containing diatoms data
                - paper_image_urls: List of image URLs from the paper
        """
        # Get paper info
        part1_prompt = self.part1_create_paper_info_json_from_pdf_text_content_prompt()
        part1_messages = self.part1_create_messages_for_paper_info_json(full_text, part1_prompt)
        paper_info = self.get_completion(part1_messages)
        
        # Extract image URLs
        paper_image_urls = paper_info.get("paper_image_urls", [])
        
        # Create diatoms data for each image URL using species information
        diatoms_data_array = []
        for image_url in paper_image_urls:
            species_array = paper_info.get("diatom_species_array", [])
            
            info_array = []
            for species in species_array:
                info_entry = {
                    "label": [f"{species['species_index']} {species['formatted_species_name']}"],
                    "index": species['species_index'],
                    "species": species['formatted_species_name'],
                    "bbox": "",
                    "yolo_bbox": "",
                    "segmentation": "",
                    "embeddings": ""
                }
                info_array.append(info_entry)
            
            diatom_data = {
                "image_url": image_url,
                "image_width": "",
                "image_height": "",
                "info": info_array
            }
            diatoms_data_array.append(diatom_data)
        
        # Package the diatoms data
        paper_diatoms_data = {
            "diatoms_data": diatoms_data_array
        }
        
        return paper_info, paper_diatoms_data, paper_image_urls

    # Storage Methods
    def get_storage_client(self):
        """
        Get authenticated Google Cloud Storage client.

        Returns:
            storage.Client: Authenticated GCS client
        """
        return storage.Client.from_service_account_info(json.loads(self.secret_json))

    def get_public_urls(self, bucket_name: str, session_id: str) -> List[str]:
        """
        Generate public URLs for all files in a specific GCS path.

        Args:
            bucket_name (str): Name of the GCS bucket
            session_id (str): Session identifier for the path prefix

        Returns:
            list: List of public URLs for the files
        """
        try:
            client = self.get_storage_client()
            bucket = client.bucket(bucket_name)
            blobs = bucket.list_blobs(prefix=f"pdf/{session_id}/")
            return [f"https://storage.googleapis.com/{bucket_name}/{blob.name}" for blob in blobs]
        
        except Exception as e:
            logger.error(f"Error retrieving public URLs: {e}")
            return []

    def load_paper_json_files(self, papers_json_public_url: str) -> List[Dict[str, Any]]:
        """
        Load existing paper JSON files from GCS.

        Args:
            papers_json_public_url (str): Public URL of the JSON files

        Returns:
            list: List of paper JSON objects
        """
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
            logger.error(f"Error loading paper JSON files: {str(e)}")
        return []

    def save_paper_json_files(self, papers_json_public_url: str, 
                            paper_json_files: List[Dict[str, Any]]) -> str:
        """
        Save paper JSON files to GCS.

        Args:
            papers_json_public_url (str): Public URL where files should be saved
            paper_json_files (list): List of paper JSON objects to save

        Returns:
            str: Public URL where files were saved, or empty string on error
        """
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
            logger.error(f"Error saving paper JSON files: {str(e)}")
            return ""

    # Prompt Generation Methods
    @staticmethod
    def part0_get_citation_info_for_paper() -> str:
        """
        Creates a structured prompt for Claude to process citation information.
        Returns a string containing the prompt with instructions and expected JSON structure.
        """
        prompt = """
        Please analyze the provided paper information to extract citation details.
        Return the data in the following JSON structure, maintaining strict adherence to the schema:
        
        {
            "authors": ["List of authors in citation format"],
            "year": "Publication year as string",
            "title": "Full title of the work",
            "type": "article/report/book/chapter",
            "journal_name": "Full journal name",
            "journal_volume": "Volume number as string",
            "journal_issue": "Issue number as string",
            "journal_pages": "Page range or total pages as string",
            "org_name": "Publishing institution/organization",
            "org_report_number": "Report ID/number",
            "digital_doi": "Digital Object Identifier if available",
            "digital_url": "Direct URL to publication",
            "formatted_citation": "Complete formatted citation string"
        }

        Important instructions:
        1. Extract all information exactly as presented in the source text
        2. Use proper citation formatting for author names (Last, First M.)
        3. Leave empty strings for missing information rather than omitting fields
        4. Ensure all JSON fields are properly quoted and formatted
        5. Verify URLs are complete and valid
        6. Follow standard citation formatting guidelines
        
        Parse the provided information and return only the JSON object without any additional text or explanation.
        """
        return prompt

    @staticmethod
    def part1_create_paper_info_json_from_pdf_text_content_prompt() -> str:
        """
        Create a structured prompt for processing diatom data.

        Returns:
            str: Prompt with instructions and expected JSON structure
        """
        return """
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
            "paper_image_urls": ["Array of image URLs from the paper"],
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
                        }
                    ],
                    "formatted_species_name": "Diploneis_bombus",
                    "genus": "Diploneis",
                    "species_magnification": "1000",
                    "species_scale_bar_microns": "30",
                    "species_note": ""
                }
                
                Repeat as necessary to get all the diatom species 
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

    @staticmethod
    def part1_create_messages_for_paper_info_json(pdf_text_content: str, 
                                                prompt: str) -> List[Dict[str, Any]]:
        """
        Create the message array for the Claude API request.

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

    @staticmethod
    def part2_create_diatoms_data_object_for_paper() -> str:
        """
        Create a structured prompt for processing diatom data.

        Returns:
            str: Prompt with instructions and expected JSON structure
        """
        return """
        Please analyze the provided paper information and image URLs to extract information about diatoms.
        Return the data in the following JSON structure, maintaining strict adherence to the schema:

        {
            "diatoms_data": [
                {
                    "image_url": "URL from paper_image_urls",
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
                        
                        Repeat as necessary to get all the diatom species 
                    ]
                }
            ]
        }

        Important instructions:
        1. Create a diatoms_data entry for each image URL in paper_image_urls
        2. For each image, include ALL species from the diatom_species_array
        3. Use species_index and formatted_species_name to create the label and species fields
        4. Ensure image_url is properly set from paper_image_urls
        5. Leave empty strings for missing information rather than omitting fields
        6. Ensure all JSON fields are properly quoted and formatted

        Parse the provided information and return only the JSON object without any additional text or explanation.
        """

    @staticmethod
    def part2_create_messages_for_diatoms_data_object_creation(
            paper_info: Dict[str, Any],
            paper_image_urls: List[str],
            prompt: str) -> List[Dict[str, Any]]:
        """
        Create the message array for the Claude API request.

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

    @staticmethod
    def get_default_citation() -> Dict[str, str]:
        """
        Returns a dictionary containing default citation information for the Stidolph Diatom Atlas.
        This serves as both an example and a fallback data structure.
        """
        return {
            "authors": ["S.R. Stidolph", "F.A.S. Sterrenburg", "K.E.L. Smith", "A. Kraberg"],
            "year": "2012",
            "title": "Stuart R. Stidolph Diatom Atlas",
            "type": "report",
            "journal_name": "",
            "journal_volume": "",
            "journal_issue": "",
            "journal_pages": "199",
            "org_name": "U.S. Geological Survey",
            "org_report_number": "Open-File Report 2012-1163",
            "digital_doi": "",
            "digital_url": "http://pubs.usgs.gov/of/2012/1163/",
            "formatted_citation": "Stidolph, S.R., Sterrenburg, F.A.S., Smith, K.E.L., Kraberg, A., 2012, Stuart R. Stidolph Diatom Atlas: U.S. Geological Survey Open-File Report 2012-1163, 199 p., available at http://pubs.usgs.gov/of/2012/1163/"
        }
  
    @staticmethod
    def extract_citation(first_two_pages_text: str, method: str = "default_citation") -> Dict[str, Any]:
        """
        Extract citation information from the first two pages of text using specified method.
        
        Args:
            first_two_pages_text: Text content from first two pages of PDF
            method: Method to use for citation extraction. 
                Options: "default_citation" or "citation_from_llm"
        
        Returns:
            Dictionary containing citation information in standardized format
            
        Raises:
            ValueError: If invalid method is specified
        """
        if method == "default_citation":
            return ClaudeAI.get_default_citation()
        
        elif method == "citation_from_llm":
            # Since this is a static method, we need to instantiate ClaudeAI
            claude_instance = ClaudeAI()
            
            # Get the citation extraction prompt
            prompt = ClaudeAI.part0_get_citation_info_for_paper()
            
            # Create messages for the API request
            messages = ClaudeAI.part1_create_messages_for_paper_info_json(
                first_two_pages_text, 
                prompt
            )
            
            try:
                # Get completion from Claude API using the instance method
                citation_json = claude_instance.get_completion(messages)
                return citation_json
                
            except Exception as e:
                logger.error(f"Error during citation extraction: {str(e)}")
                return ClaudeAI.get_default_citation()
                    
        else:
            raise ValueError("Invalid method. Use 'default_citation' or 'citation_from_llm'")
            
    def get_diatoms_data(self, json_url: str) -> List[Dict[str, Any]]:
        """
        Load JSON data from URL and extract diatoms_data into an array.

        Args:
            json_url (str): URL of the JSON data

        Returns:
            list: Array of diatoms data objects
        """
        diatoms_data_array = []
        
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
                            logger.warning(f"Skipping invalid JSON in diatoms_data")
                            continue
                    
                    diatoms_data_array.append(diatoms_data)
            
            logger.info(f"Successfully extracted diatoms data from {len(diatoms_data_array)} papers")
            return diatoms_data_array
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching data from URL: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON data: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
        
        return []

    def update_and_save_papers(self, json_url: str, paper_json_files: List[Dict[str, Any]], 
                             diatoms_data: List[Dict[str, Any]]) -> bool:
        """
        Update papers JSON with modified diatoms_data and save back to GCS.

        Args:
            json_url (str): URL where the JSON should be saved
            paper_json_files (list): List of paper JSON objects
            diatoms_data (list): List of diatoms data objects

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            diatoms_data_map = {data['image_url']: data for data in diatoms_data}
            
            for paper in paper_json_files:
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
            
            json_content = json.dumps(paper_json_files, indent=2)
            
            blob.upload_from_string(
                json_content,
                content_type='application/json'
            )
            
            logger.info(f"Successfully updated and saved papers JSON to: {json_url}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating and saving papers: {str(e)}")
            return False