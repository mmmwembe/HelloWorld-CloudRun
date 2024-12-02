from flask import Flask, render_template, send_file, request, jsonify, redirect, url_for, flash, send_from_directory
import os
from datetime import datetime
import time
import json
import tempfile
from threading import Thread, Lock
from modules.installed_packages import get_installed_packages
from modules import ClaudeAI
from modules import GCPOps
from modules import PDFOps

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Constants
SESSION_ID = 'eb9db0ca54e94dbc82cffdab497cde13'
PAPERS_BUCKET = 'papers-diatoms'
PAPERS_PROCESSED_BUCKET = 'papers-diatoms-processed'
PAPERS_BUCKET_LABELLING = 'papers-diatoms-labelling'
PAPERS_BUCKET_JSON_FILES = 'papers-diatoms-jsons'
BUCKET_EXTRACTED_IMAGES = 'papers-extracted-images-bucket-mmm'
BUCKET_PAPER_TRACKER_CSV = 'papers-extracted-pages-csv-bucket-mmm'

# Global variables for data management
PAPERS_JSON_PUBLIC_URL = f"https://storage.googleapis.com/{PAPERS_BUCKET_JSON_FILES}/jsons_from_pdfs/{SESSION_ID}/{SESSION_ID}.json"
PAPER_JSON_FILES = []
DIATOMS_DATA = []
data_lock = Lock()

# Create an instance of GCPOps
gcp_ops = GCPOps()

# Initialize the uploaded PDF files DataFrame
UPLOADED_PDF_FILES_DF = gcp_ops.initialize_paper_upload_tracker_df_from_gcp(
    session_id=SESSION_ID,
    bucket_name=BUCKET_PAPER_TRACKER_CSV
)

def initialize_data():
    """Initialize global data structures with thread safety"""
    global PAPER_JSON_FILES, DIATOMS_DATA
    
    with data_lock:
        try:
            # Check if the URL exists first
            if not gcp_ops.check_gcs_file_exists(PAPERS_JSON_PUBLIC_URL):
                app.logger.warning(f"No data file found at {PAPERS_JSON_PUBLIC_URL}, initializing empty data structures")
                PAPER_JSON_FILES = []
                DIATOMS_DATA = []
                return

            # Load data if file exists
            PAPER_JSON_FILES = gcp_ops.load_paper_json_files(PAPERS_JSON_PUBLIC_URL)
            if PAPER_JSON_FILES:
                DIATOMS_DATA = ClaudeAI.get_DIATOMS_DATA(PAPERS_JSON_PUBLIC_URL)
                app.logger.info(f"Successfully loaded {len(DIATOMS_DATA)} diatom entries")
            else:
                DIATOMS_DATA = []
                app.logger.warning("No paper JSON files found, initializing empty data structures")
                
        except Exception as e:
            app.logger.error(f"Error initializing data: {str(e)}")
            PAPER_JSON_FILES = []
            DIATOMS_DATA = []

def safe_value(value):
    """Safely handle potentially None values"""
    return value if value else ""

@app.before_request
def ensure_data_initialized():
    """Ensure data is initialized before handling requests"""
    global DIATOMS_DATA, PAPER_JSON_FILES
    
    # Skip for static files and certain routes
    if request.path.startswith('/static/') or request.path in ['/', '/modules']:
        return
        
    # Check if data structures are empty
    with data_lock:
        if not DIATOMS_DATA and not PAPER_JSON_FILES:
            app.logger.warning("Data structures not initialized, reinitializing...")
            initialize_data()


# Create an instance of GCPOps
gcp_ops = GCPOps()

# Initialize the uploaded PDF files DataFrame
UPLOADED_PDF_FILES_DF = gcp_ops.initialize_paper_upload_tracker_df_from_gcp(
    session_id=SESSION_ID,
    bucket_name=BUCKET_PAPER_TRACKER_CSV
)

def get_paper_image_urls(metadata):
    """Extract paper image URLs from metadata"""
    if not isinstance(metadata, dict):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            app.logger.error("Failed to parse metadata JSON")
            return []
    return metadata.get("paper_image_urls", [])

def parse_output(output):
    """Parse JSON output from string"""
    stripped_output = output.strip("```").strip()
    start_idx = stripped_output.find("{")
    if start_idx != -1:
        stripped_output = stripped_output[start_idx:]
    try:
        return json.loads(stripped_output)
    except json.JSONDecodeError as e:
        app.logger.error(f"Error parsing JSON output: {str(e)}")
        return None

# Processing status tracking
processing_status = {
    'current_index': 0,
    'current_url': '',
    'complete': False,
    'total_pdfs': 0,
    'full_text': '',
    'first_two_pages_text': '',
    'filename': '',
    'citation_info': '',
    'extracted_images_file_metadata': '',
    'pdf_paper_json': '',
    'paper_info': '',
    'diatoms_data': '',
}

def process_pdfs(pdf_urls):
    """Background task to process PDFs"""
    global processing_status, PAPER_JSON_FILES
    
    for i, url in enumerate(pdf_urls, 1):
        processing_status['current_index'] = i
        processing_status['current_url'] = url
        
        try:
            pdf_ops = PDFOps()
            claude = ClaudeAI()
            
            papers_json_public_url = f"https://storage.googleapis.com/{PAPERS_BUCKET_JSON_FILES}/jsons_from_pdfs/{SESSION_ID}/{SESSION_ID}.json"
    
            # Load existing PAPER_JSON_FILES
            PAPER_JSON_FILES = gcp_ops.load_paper_json_files(papers_json_public_url)
            
            # Extract text and images
            full_text, first_two_pages_text, filename = pdf_ops.extract_text_from_pdf(url)
            extracted_images_file_metadata = pdf_ops.extract_images_and_metadata(url, SESSION_ID, BUCKET_EXTRACTED_IMAGES)
            
            # Process paper
            paper_info, diatoms_data, paper_image_urls = claude.process_paper(full_text, extracted_images_file_metadata)
            
            # Get citation info
            citation_info = claude.extract_citation(first_two_pages_text=first_two_pages_text, method="default_citation")
            
            # Create paper JSON
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
            
            # Update PAPER_JSON_FILES and save
            PAPER_JSON_FILES.append(pdf_paper_json)
            papers_json_public_url = gcp_ops.save_paper_json_files(papers_json_public_url, PAPER_JSON_FILES)
            
            # Update processing status
            processing_status.update({
                'full_text': full_text,
                'first_two_pages_text': first_two_pages_text,
                'filename': filename,
                'citation_info': json.dumps(citation_info, indent=2),
                'extracted_images_file_metadata': json.dumps(extracted_images_file_metadata, indent=2),
                'pdf_paper_json': json.dumps(pdf_paper_json, indent=2),
                'paper_info': json.dumps(paper_info, indent=2),
                'diatoms_data': json.dumps(diatoms_data, indent=2)
            })
            
        except Exception as e:
            app.logger.error(f"Error processing PDF: {str(e)}")
            processing_status.update({
                'full_text': 'Error extracting text',
                'first_two_pages_text': 'Error extracting text',
                'filename': 'Error extracting filename',
                'citation_info': 'Error extracting citation',
                'extracted_images_file_metadata': 'Error extracting images and file metadata',
                'pdf_paper_json': 'Error generating pdf_paper_json',
                'paper_info': 'Error generating paper_info',
                'diatoms_data': 'Error generating diatoms_data'
            })
            
        time.sleep(15)
    
    processing_status['complete'] = True

def save_labels(updated_data):
    """Save updated labels and synchronize all data structures"""
    global PAPER_JSON_FILES, DIATOMS_DATA
    
    try:
        # Update DIATOMS_DATA with new label information
        image_index = updated_data.get('image_index', 0)
        info = updated_data.get('info', [])
        
        if 0 <= image_index < len(DIATOMS_DATA):
            DIATOMS_DATA[image_index]['info'] = info
            
            # Update corresponding entry in PAPER_JSON_FILES
            for paper in PAPER_JSON_FILES:
                if 'diatoms_data' in paper:
                    # Convert string to dict if necessary
                    if isinstance(paper['diatoms_data'], str):
                        paper['diatoms_data'] = json.loads(paper['diatoms_data'])
                    
                    # Update the diatoms data
                    if paper['diatoms_data'].get('image_url') == DIATOMS_DATA[image_index].get('image_url'):
                        paper['diatoms_data']['info'] = info
                        break
            
            # Save updated data to GCS
            success = ClaudeAI.update_and_save_papers(
                PAPERS_JSON_PUBLIC_URL,
                PAPER_JSON_FILES,
                DIATOMS_DATA
            )
            
            if not success:
                raise Exception("Failed to save updates to GCS")
                
            return True
            
    except Exception as e:
        app.logger.error(f"Error saving labels: {str(e)}")
        raise
        
    return False


# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/modules')
def modules():
    installed_packages = get_installed_packages()
    return render_template('modules.html', packages=installed_packages)

@app.route('/download_installed_pkgs')
def download_installed_pkgs():
    installed_packages = get_installed_packages()
    formatted_data = "\n".join(f"{name}: {version}" for name, version in installed_packages.items())
    
    current_date = datetime.now().strftime('%m-%d-%y')
    filename = f"Installed_Packages_{current_date}.txt"
    
    os.makedirs("temp_uploads", exist_ok=True)
    file_path = os.path.join("temp_uploads", filename)
    
    with open(file_path, 'w') as file:
        file.write(formatted_data)
    
    return send_file(file_path, as_attachment=True)

@app.route('/all_papers')
def all_papers():
    try:
        claude = ClaudeAI()
        pdf_urls = claude.get_public_urls(PAPERS_BUCKET, SESSION_ID)
        return render_template('papers.html', pdf_urls=pdf_urls)
    except Exception as e:
        return render_template('papers.html', pdf_urls=[], error=f"Unable to retrieve papers: {str(e)}")

@app.route('/process_pdfs', methods=['POST'])
def start_processing():
    global processing_status
    
    try:
        pdf_urls = json.loads(request.form.get('pdf_urls', '[]'))
        
        if not pdf_urls:
            return render_template('papers.html', error="No PDFs to process")
        
        processing_status.update({
            'current_index': 0,
            'current_url': '',
            'complete': False,
            'total_pdfs': len(pdf_urls)
        })
        
        Thread(target=process_pdfs, args=(pdf_urls,)).start()
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

@app.route('/view_uploaded_pdfs')
def view_uploaded_pdfs():
    try:
        return send_from_directory('templates', 'view_uploaded_pdfs.html')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pdf_data')
def get_pdf_data():
    try:
        pdf_data = UPLOADED_PDF_FILES_DF.to_dict(orient='records')
        return jsonify(pdf_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/diatoms_data')
def see_diatoms_data():
    try:
        if not PAPERS_BUCKET_JSON_FILES or not SESSION_ID:
            raise ValueError("Required configuration variables are not set")
        
        papers_json_public_url = f"https://storage.googleapis.com/{PAPERS_BUCKET_JSON_FILES}/jsons_from_pdfs/{SESSION_ID}/{SESSION_ID}.json"
        DIATOMS_DATA = ClaudeAI.get_DIATOMS_DATA(papers_json_public_url)
        
        if not DIATOMS_DATA:
            raise ValueError("No diatoms data retrieved")
            
        return render_template('diatoms_data.html', 
                             json_url=papers_json_public_url,
                             diatoms_data=DIATOMS_DATA)
    except Exception as e:
        app.logger.error(f"Error in diatoms_data route: {str(e)}")
        return render_template('error.html', error=str(e)), 500

@app.route('/label', methods=['GET', 'POST'])
def label():
    if request.method == 'POST':
        updated_data = request.json
        save_labels(updated_data)
        return jsonify({'success': True})
    
    return render_template('label-react.html')

@app.route('/api/diatoms', methods=['GET'])
def get_diatoms():
    try:
        image_index = request.args.get('index', 0, type=int)
        current_data = DIATOMS_DATA
        
        # Check if we have any data
        if not current_data:
            return jsonify({
                'current_index': 0,
                'total_images': 0,
                'data': {},
                'error': 'No diatoms data available'
            })
        
        # Ensure index is within bounds
        total_images = len(current_data)
        image_index = min(max(0, image_index), total_images - 1)
        
        # Get the data for the current index
        try:
            current_image_data = current_data[image_index]
        except IndexError:
            app.logger.error(f"Failed to get data for index {image_index} from list of length {total_images}")
            return jsonify({
                'current_index': 0,
                'total_images': total_images,
                'data': {},
                'error': 'Invalid image index'
            })
        
        return jsonify({
            'current_index': image_index,
            'total_images': total_images,
            'data': current_image_data
        })
        
    except Exception as e:
        app.logger.error(f"Error in get_diatoms: {str(e)}")
        return jsonify({
            'current_index': 0,
            'total_images': 0,
            'data': {},
            'error': f'Error retrieving diatoms data: {str(e)}'
        }), 500

@app.route('/api/save', methods=['POST'])
def save():
    try:
        update_data = request.json
        success = save_labels(update_data)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Labels saved successfully',
                'timestamp': datetime.now().isoformat(),
                'saved_index': update_data.get('image_index', 0),
                'gcp_url': PAPERS_JSON_PUBLIC_URL
            })
        else:
            raise Exception("Failed to save labels")
            
    except Exception as e:
        app.logger.error(f"Error in save endpoint: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/download', methods=['GET'])
def download_labels():
    """Download the saved labels file for current session"""
    try:
        # Create a temporary file for download
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(DIATOMS_DATA, temp_file, indent=4)
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

@app.route('/json')
def display_json():
    return render_template('displayjson.html')

# Initialize data when the app starts
@app.before_first_request
def setup():
    initialize_data()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, threaded=True)