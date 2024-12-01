from flask import Flask, render_template, send_file, request, jsonify, redirect, url_for, flash, send_from_directory
import os
from datetime import datetime
import time
import json
import tempfile
from threading import Thread
from modules.installed_packages import get_installed_packages
from modules import ClaudeAI
from modules import GCPOps
from modules import PDFOps  # Add this import at the top

app = Flask(__name__)

# Constants
SESSION_ID = 'eb9db0ca54e94dbc82cffdab497cde13'
PAPERS_BUCKET = 'papers-diatoms'
PAPERS_PROCESSED_BUCKET ='papers-diatoms-processed'
PAPERS_BUCKET_LABELLING ='papers-diatoms-labelling'
PAPERS_BUCKET_JSON_FILES ='papers-diatoms-jsons'
BUCKET_EXTRACTED_IMAGES = 'papers-extracted-images-bucket-mmm'
BUCKET_PAPER_TRACKER_CSV = 'papers-extracted-pages-csv-bucket-mmm'

DIATOMS_DATA =[]

def safe_value(value):
    return value if value else ""

# Create an instance of GCPOps
gcp_ops = GCPOps()

# Call the method with the new variable name
UPLOADED_PDF_FILES_DF = gcp_ops.initialize_paper_upload_tracker_df_from_gcp(
    session_id=SESSION_ID,
    bucket_name=BUCKET_PAPER_TRACKER_CSV
)

def get_paper_image_urls(metadata):
    """
    Ensures the input metadata is a dictionary, parses it as JSON if necessary,
    and returns the value of the `paper_image_urls` key.

    Args:
        metadata (dict or str): The metadata input, either as a dictionary or a JSON string.

    Returns:
        list: The value of the `paper_image_urls` key, or an empty list if not found.
    """
    if not isinstance(metadata, dict):
        try:
            # Attempt to parse metadata as JSON
            metadata = json.loads(metadata)
            print("metadata has been converted to a dictionary.")
        except json.JSONDecodeError:
            print("Failed to convert metadata to a dictionary. Ensure it is in valid JSON format.")
            return []  # Return an empty list if parsing fails

    # Return the value of `paper_image_urls` or an empty list if the key is missing
    return metadata.get("paper_image_urls", [])

def parse_output(output):
    """
    Parses a string containing JSON, stripping unnecessary prefixes or code fences.

    Args:
        output (str): The input string containing JSON.

    Returns:
        dict or None: The parsed JSON as a dictionary, or None if parsing fails.
    """
    stripped_output = output.strip("```").strip()

    # Find the start of JSON content
    start_idx = stripped_output.find("{")
    if start_idx != -1:
        stripped_output = stripped_output[start_idx:]

    try:
        output_dict = json.loads(stripped_output)
        return output_dict
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON output: {str(e)}")
        print("Content:")
        print(repr(stripped_output))  # Use repr to make debugging easier
        return None

processing_status = {
    'current_index': 0,
    'current_url': '',
    'complete': False,
    'total_pdfs': 0,
    'full_text': '',
    'first_two_pages_text': '',
    'filename': '',
    'citation_info': '',
    'extracted_images_file_metadata':'',
    'pdf_paper_json': '',
    'paper_info':'',
    'diatoms_data':'',
}

def process_pdfs(pdf_urls):
    """Background task to process PDFs"""
    global processing_status
    
    for i, url in enumerate(pdf_urls, 1):
        processing_status['current_index'] = i
        processing_status['current_url'] = url
        
        # Initialize PDFOps and extract text
        try:
            pdf_ops = PDFOps()
            claude = ClaudeAI()
            
            papers_json_public_url = f"https://storage.googleapis.com/{PAPERS_BUCKET_JSON_FILES}/jsons_from_pdfs/{SESSION_ID}/{SESSION_ID}.json"
    
            # Load existing PAPER_JSON_FILES
            PAPER_JSON_FILES = gcp_ops.load_paper_json_files(papers_json_public_url)
            
            # Get text content
            full_text, first_two_pages_text, filename = pdf_ops.extract_text_from_pdf(url)
            extracted_images_file_metadata = pdf_ops.extract_images_and_metadata(url, SESSION_ID, BUCKET_EXTRACTED_IMAGES)
            
            # Get paper_info 
            paper_info, diatoms_data, paper_image_urls = claude.process_paper(full_text,extracted_images_file_metadata)

            
            # Get citation info. Available methods: (a) "default_citation" - Returns predefined Stidolph Diatom Atlas citation
            # (b) "citation_from_llm": Uses Claude to extract citation from the text
            #citation_info = claude.get_default_citation()
            citation_info = claude.extract_citation(first_two_pages_text=first_two_pages_text, method="default_citation")
            #citation_info = claude.extract_citation(first_two_pages_text=first_two_pages_text, method="citation_from_llm")
            
            pdf_paper_json = {
                "pdf_file_url": safe_value(url),
                "filename": safe_value(filename),
                "extracted_images_file_metadata": safe_value(extracted_images_file_metadata),
                "pdf_text_content": safe_value(full_text),
                "first_two_pages_text": safe_value(first_two_pages_text),
                "paper_info": safe_value(paper_info),
                "papers_json_public_url": safe_value(papers_json_public_url),
                "diatoms_data": safe_value(diatoms_data),
                "citation": safe_value(citation_info)
            }
            
            
                    # Check if paper already exists in PAPER_JSON_FILES
            if not any(paper['pdf_file_url'] ==url for paper in PAPER_JSON_FILES):
                PAPER_JSON_FILES.append(pdf_paper_json)
                
            # Save updated PAPER_JSON_FILES
            papers_json_public_url = gcp_ops.save_paper_json_files(papers_json_public_url, PAPER_JSON_FILES)
            
            
            # Update processing status with new information
            processing_status['full_text'] = full_text
            processing_status['first_two_pages_text'] = first_two_pages_text
            processing_status['filename'] = filename
            processing_status['citation_info'] = json.dumps(citation_info, indent=2)
            processing_status['extracted_images_file_metadata'] = json.dumps(extracted_images_file_metadata, indent=2)
            processing_status['pdf_paper_json'] = json.dumps(pdf_paper_json, indent=2)            
            processing_status['paper_info'] = json.dumps(paper_info, indent=2)                
            processing_status['diatoms_data'] = json.dumps(diatoms_data, indent=2)    
                        
        except Exception as e:
            print(f"Error processing PDF: {str(e)}")
            processing_status['full_text'] = 'Error extracting text'
            processing_status['first_two_pages_text'] = 'Error extracting text'
            processing_status['filename'] = 'Error extracting filename'
            processing_status['citation_info'] = 'Error extracting citation'
            processing_status['extracted_images_file_metadata'] = 'Error extracting images and file metadata'            
            processing_status['pdf_paper_json'] = 'Error generating pdf_paper_json'      
            processing_status['paper_info'] = 'Error generating paper_info'     
            processing_status['diatoms_data'] = 'Error generating diatoms_data'   
                        
        # Simulate processing time
        time.sleep(25)
    
    processing_status['complete'] = True



@app.route('/')
def index():
    return render_template('index.html')

@app.route('/modules')
def modules():
    # Get the installed packages
    installed_packages = get_installed_packages()
    
    # Render the packages in the modules.html template
    return render_template('modules.html', packages=installed_packages)

@app.route('/download_installed_pkgs')
def download_installed_pkgs():
    # Get the installed packages
    installed_packages = get_installed_packages()
    
    # Format the data as text
    formatted_data = "\n".join(f"{name}: {version}" for name, version in installed_packages.items())
    
    # Create the filename with the current date
    current_date = datetime.now().strftime('%m-%d-%y')
    filename = f"Installed_Packages_{current_date}.txt"
    
    # Create temp_uploads directory if it doesn't exist
    os.makedirs("temp_uploads", exist_ok=True)
    file_path = os.path.join("temp_uploads", filename)
    
    # Write the data to the file
    with open(file_path, 'w') as file:
        file.write(formatted_data)
    
    # Return the file for download
    return send_file(file_path, as_attachment=True)

@app.route('/all_papers')
def all_papers():
    try:
        # Initialize ClaudeAI instance
        claude = ClaudeAI()
        
        # Get public URLs for all PDFs
        pdf_urls = claude.get_public_urls(PAPERS_BUCKET, SESSION_ID)
        
        # Render template with URLs
        return render_template('papers.html', pdf_urls=pdf_urls)
    except Exception as e:
        # Render template with error message
        return render_template('papers.html', 
                             pdf_urls=[], 
                             error=f"Unable to retrieve papers: {str(e)}")

@app.route('/process_pdfs', methods=['POST'])
def start_processing():
    global processing_status
    
    try:
        # Get PDF URLs from form and parse JSON
        pdf_urls = json.loads(request.form.get('pdf_urls', '[]'))
        
        if not pdf_urls:
            return render_template('papers.html', error="No PDFs to process")
        
        # Reset processing status
        processing_status['current_index'] = 0
        processing_status['current_url'] = ''
        processing_status['complete'] = False
        processing_status['total_pdfs'] = len(pdf_urls)
        
        # Start processing in background
        Thread(target=process_pdfs, args=(pdf_urls,)).start()
        
        # Redirect to processing page
        return redirect(url_for('show_processing'))
    except json.JSONDecodeError as e:
        return render_template('papers.html', error=f"Invalid PDF data format: {str(e)}")
    except Exception as e:
        return render_template('papers.html', error=f"Error starting processing: {str(e)}")

@app.route('/processing')
def show_processing():
    return render_template('processing.html')

@app.route('/process_status')
def get_process_status():
    return jsonify(processing_status)

@app.route('/complete')
def complete():
    return render_template('complete.html')



from flask import send_from_directory, jsonify

@app.route('/view_uploaded_pdfs')
def view_uploaded_pdfs():
    try:
        # Assuming your HTML file is in the templates directory
        return send_from_directory('templates', 'view_uploaded_pdfs.html')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pdf_data')
def get_pdf_data():
    try:
        # Add debugging log
        print(f"DataFrame size: {len(UPLOADED_PDF_FILES_DF)}")
        
        # Convert DataFrame to dictionary format
        pdf_data = UPLOADED_PDF_FILES_DF.to_dict(orient='records')
        
        # Add debugging log
        print(f"Sending {len(pdf_data)} records")
        
        return jsonify(pdf_data)
    except Exception as e:
        print(f"Error in get_pdf_data: {str(e)}")  # Add error logging
        return jsonify({'error': str(e)}), 500


@app.route('/diatoms_data')
def see_diatoms_data():
    try:
        # Check if required variables are defined
        if not PAPERS_BUCKET_JSON_FILES or not SESSION_ID:
            raise ValueError("Required configuration variables are not set")
            
        papers_json_public_url = f"https://storage.googleapis.com/{PAPERS_BUCKET_JSON_FILES}/jsons_from_pdfs/{SESSION_ID}/{SESSION_ID}.json"
        
        DIATOMS_DATA = ClaudeAI.get_DIATOMS_DATA(papers_json_public_url)
        
        # Check if we got valid data
        if not DIATOMS_DATA:
            raise ValueError("No diatoms data retrieved")
            
        return render_template('diatoms_data.html', 
                             json_url=papers_json_public_url, 
                             diatoms_data=DIATOMS_DATA)
                             
    except Exception as e:
        app.logger.error(f"Error in diatoms_data route: {str(e)}")
        # Return an error page or redirect to a safe page
        return render_template('error.html', error=str(e)), 500


#________________________________Labelling_____________________________________________
papers_json_public_url = f"https://storage.googleapis.com/{PAPERS_BUCKET_JSON_FILES}/jsons_from_pdfs/{SESSION_ID}/{SESSION_ID}.json"

diatoms_data = ClaudeAI.get_DIATOMS_DATA(papers_json_public_url)

def load_saved_labels():
    """Load saved labels for current session if they exist"""
    try:
        json_public_url = f"https://storage.googleapis.com/{PAPERS_BUCKET_LABELLING}/labels/{SESSION_ID}/{SESSION_ID}.json"
        DIATOMS_DATA = ClaudeAI.get_DIATOMS_DATA(json_public_url)
        return DIATOMS_DATA
    except Exception as e:
        print(f"Error loading from GCP: {e}")
        return diatoms_data  # Return base data if loading fails

def save_labels(data):
    """Save labels for current session to GCP storage"""
    try:
        # Create a temporary file to upload
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(data, temp_file, indent=4)
            temp_path = temp_file.name
        
        # Upload to GCP and then delete temporary file
        gcp_ops.save_json_to_bucket(temp_path, PAPERS_BUCKET_LABELLING, SESSION_ID)
        os.unlink(temp_path)
    except Exception as e:
        print(f"Error saving to GCP: {e}")
        raise

@app.route('/label', methods=['GET', 'POST'])
def label():
    if request.method == 'POST':
        updated_data = request.json
        save_labels(updated_data)
        return jsonify({'success': True})
    
    return render_template('label-react.html')

@app.route('/api/diatoms', methods=['GET'])
def get_diatoms():
    image_index = request.args.get('index', 0, type=int)
    
    # Load current session's data
    current_data = load_saved_labels()
    
    # Ensure index is within bounds
    image_index = min(max(0, image_index), len(current_data) - 1)
    
    return jsonify({
        'current_index': image_index,
        'total_images': len(current_data),
        'data': current_data[image_index]
    })

@app.route('/api/save', methods=['POST'])
def save():
    try:
        current_data = load_saved_labels()
        image_index = request.json.get('image_index', 0)
        updated_info = request.json.get('info', [])
        
        # Update only the info for the current image
        current_data[image_index]['info'] = updated_info
        
        # Save the updated dataset
        save_labels(current_data)
        
        return jsonify({
            'success': True,
            'message': 'Labels saved successfully',
            'timestamp': datetime.now().isoformat(),
            'saved_index': image_index,
            'gcp_url': f"https://storage.googleapis.com/{PAPERS_BUCKET_LABELLING}/labels/{SESSION_ID}/{SESSION_ID}.json"
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/download', methods=['GET'])
def download_labels():
    """Download the saved labels file for current session"""
    try:
        json_public_url = f"https://storage.googleapis.com/{PAPERS_BUCKET_LABELLING}/labels/{SESSION_ID}/{SESSION_ID}.json"
        data = ClaudeAI.get_DIATOMS_DATA(json_public_url)
        
        # Create a temporary file for download
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(data, temp_file, indent=4)
            temp_path = temp_file.name
        
        try:
            # Send the file and then clean up
            response = send_file(
                temp_path,
                mimetype='application/json',
                as_attachment=True,
                download_name=f'diatom_labels_{SESSION_ID}.json'
            )
            # Clean up temp file after sending
            os.unlink(temp_path)
            return response
        except Exception as e:
            # Clean up temp file if sending fails
            os.unlink(temp_path)
            raise e
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

#________________________________Labelling_____________________________________________

@app.route('/json')
def display_json():
    return render_template('displayjson.html')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, threaded=True)