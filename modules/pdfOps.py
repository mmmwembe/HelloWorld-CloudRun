import os
import tempfile
import requests
import hashlib
import shutil
import json
from typing import Optional, Dict, Any
import fitz  # PyMuPDF
from PyPDF2 import PdfReader
from google.cloud import storage
from dotenv import load_dotenv

class PDFOps:
    """
    A class for handling PDF operations including text extraction, image extraction,
    and Google Cloud Storage interactions.
    """
    
    def __init__(self):
        """Initialize PDFOps with Google Cloud credentials"""
        load_dotenv()
        self.secret_json = os.getenv('GOOGLE_SECRET_JSON')
        if not self.secret_json:
            raise ValueError("GOOGLE_SECRET_JSON environment variable not found")
        
    def _get_storage_client(self) -> storage.Client:
        """
        Get authenticated Google Cloud Storage client.
        
        Returns:
            storage.Client: Authenticated GCS client
        """
        return storage.Client.from_service_account_info(json.loads(self.secret_json))
    
    @staticmethod
    def _get_file_hash(file_content: bytes) -> str:
        """
        Calculate SHA-256 hash of file content.
        
        Args:
            file_content (bytes): Content to hash
            
        Returns:
            str: SHA-256 hash of the content
        """
        return hashlib.sha256(file_content).hexdigest()
    
    def extract_text_from_pdf(self, pdf_url: str) -> str:
        """
        Downloads PDF from URL to temp directory, extracts text, then cleans up.
        
        Args:
            pdf_url (str): The URL of the PDF file
        
        Returns:
            str: Extracted text from the PDF
        """
        temp_dir = None
        try:
            # Create temporary file with proper extension
            temp_dir = tempfile.mkdtemp()
            temp_pdf_path = os.path.join(temp_dir, 'temp.pdf')
            
            # Download the file
            response = requests.get(pdf_url)
            response.raise_for_status()
            
            # Save to temp file
            with open(temp_pdf_path, 'wb') as f:
                f.write(response.content)
            
            # Extract text
            reader = PdfReader(temp_pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
                
            return text
            
        except Exception as e:
            print(f"Error processing PDF: {str(e)}")
            return ""
            
        finally:
            # Clean up temp directory and its contents
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def upload_to_gcs(self, image_content: bytes, filename: str, session_id: str, bucket_name: str) -> Optional[str]:
        """
        Upload image to Google Cloud Storage and return public URL.
        
        Args:
            image_content (bytes): The image content to upload
            filename (str): Name for the file in storage
            session_id (str): Session identifier for organizing uploads
            bucket_name (str): Name of the GCS bucket
            
        Returns:
            Optional[str]: Public URL of uploaded image or None if upload fails
        """
        try:
            client = self._get_storage_client()
            bucket = client.bucket(bucket_name)

            # Create blob path using session ID and filename
            blob_path = f"{session_id}/{filename}"
            blob = bucket.blob(blob_path)

            # Upload image
            blob.upload_from_string(image_content, content_type='image/jpeg')

            # Generate public URL
            public_url = f"https://storage.googleapis.com/{bucket_name}/{blob_path}"
            return public_url

        except Exception as e:
            print(f"Error uploading to GCS: {str(e)}")
            return None

    def extract_images_and_metadata(self, pdf_url: str, session_id: str, bucket_name: str) -> Optional[Dict[str, Any]]:
        """
        Extracts images and metadata from a PDF file.
        
        Args:
            pdf_url (str): URL of the PDF file
            session_id (str): Session identifier for organizing uploads
            bucket_name (str): Name of the GCS bucket for storing images
            
        Returns:
            Optional[Dict[str, Any]]: Dictionary containing extracted metadata and image URLs
        """
        try:
            # Convert GCS URL to direct download URL
            pdf_url = pdf_url.replace("storage.cloud.google.com", "storage.googleapis.com")

            # Create temporary directory for extracted images
            tmp_dir = "tmp_extracted_images"
            os.makedirs(tmp_dir, exist_ok=True)

            # Download PDF content
            response = requests.get(pdf_url)
            response.raise_for_status()
            pdf_content = response.content

            # Calculate file hash
            file_256_hash = self._get_file_hash(pdf_content)

            # Create temporary PDF file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_content)
                temp_path = temp_file.name

            # Open PDF with PyMuPDF
            pdf_document = fitz.open(temp_path)
            total_pages = len(pdf_document)

            # Initialize result structure
            result = {
                "file_256_hash": file_256_hash,
                "images_in_doc": [],
                "paper_image_urls": [],
                "total_images": 0,
                "page_details": []
            }

            # Process each page
            for page_num in range(total_pages):
                page = pdf_document[page_num]
                image_list = page.get_images()

                page_info = {
                    "page_index": page_num,
                    "total_pages": total_pages,
                    "has_images": len(image_list) > 0,
                    "num_images": len(image_list),
                    "image_urls": []
                }

                if image_list:
                    for img_idx, img in enumerate(image_list, 1):
                        try:
                            # Get image data
                            xref = img[0]
                            base_image = pdf_document.extract_image(xref)
                            image_bytes = base_image["image"]

                            # Create filename
                            image_filename = f"{file_256_hash}_image_{img_idx}.jpeg"

                            # Upload to GCS and get URL
                            image_url = self.upload_to_gcs(
                                image_content=image_bytes,
                                filename=image_filename,
                                session_id=session_id,
                                bucket_name=bucket_name
                            )

                            if image_url:
                                page_info["image_urls"].append(image_url)
                                result["paper_image_urls"].append(image_url)

                        except Exception as e:
                            print(f"Error processing image {img_idx} on page {page_num + 1}: {str(e)}")

                # Update total_images count
                result["total_images"] += page_info["num_images"]

                if page_info["has_images"]:
                    result["page_details"].append({
                        "page_index": page_num,
                        "num_images": page_info["num_images"],
                        "image_urls": page_info["image_urls"]
                    })

                result["images_in_doc"].append(page_info)

            # Cleanup
            pdf_document.close()
            os.unlink(temp_path)
            
            if os.path.exists(tmp_dir):
                for file in os.listdir(tmp_dir):
                    os.remove(os.path.join(tmp_dir, file))
                os.rmdir(tmp_dir)

            return result

        except Exception as e:
            print(f"Error processing PDF: {str(e)}")
            return None
        
# from modules import PDFOps

# # Initialize the PDFOps class
# pdf_ops = PDFOps()

# # Extract text from a PDF
# text = pdf_ops.extract_text_from_pdf("https://example.com/sample.pdf")

# # Extract images and metadata
# result = pdf_ops.extract_images_and_metadata(
#     pdf_url="https://example.com/sample.pdf",
#     session_id="unique_session_id",
#     bucket_name="your-gcs-bucket-name"
# )