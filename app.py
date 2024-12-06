from flask import Flask, render_template, send_file, request, jsonify, redirect, url_for, flash, send_from_directory, Response
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import time
import json
import tempfile
from threading import Thread, Lock
from modules.installed_packages import get_installed_packages
# from modules import ClaudeAI
# from modules import GCPOps
# from modules import PDFOps
from modules import ClaudeAI, GCPOps, PDFOps, SegmentationOps
import logging
import pandas as pd
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SECURITY_PASSWORD_SALT'] = 'thisistheSALTforcreatingtheCONFIRMATIONtoken'
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # Increased to 64MB for multiple files
app.config['UPLOAD_FOLDER'] = 'temp_uploads'

# Constants
SESSION_ID = 'eb9db0ca54e94dbc82cffdab497cde13'
PAPERS_BUCKET = 'papers-diatoms'
PAPERS_PROCESSED_BUCKET = 'papers-diatoms-processed'
PAPERS_BUCKET_LABELLING = 'papers-diatoms-labelling'
PAPERS_BUCKET_JSON_FILES = 'papers-diatoms-jsons'
BUCKET_EXTRACTED_IMAGES = 'papers-extracted-images-bucket-mmm'
BUCKET_PAPER_TRACKER_CSV = 'papers-extracted-pages-csv-bucket-mmm'
BUCKET_SEGMENTATION_LABELS='papers-diatoms-segmentation'

# Global variables for data management
PAPERS_JSON_PUBLIC_URL = f"https://storage.googleapis.com/{PAPERS_BUCKET_JSON_FILES}/jsons_from_pdfs/{SESSION_ID}/{SESSION_ID}.json"
PAPER_JSON_FILES = []
DIATOMS_DATA = []
data_lock = Lock()

# 
ALLOWED_EXTENSIONS = {'pdf'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Create an instance of GCPOps
gcp_ops = GCPOps()
segmentation_ops = SegmentationOps()
# Initialize the uploaded PDF files DataFrame
try:
    UPLOADED_PDF_FILES_DF = gcp_ops.initialize_paper_upload_tracker_df_from_gcp(
        session_id=SESSION_ID,
        bucket_name=BUCKET_PAPER_TRACKER_CSV
    )
    logger.info("Successfully initialized PDF files DataFrame")
except Exception as e:
    logger.error(f"Error initializing PDF files DataFrame: {str(e)}")
    UPLOADED_PDF_FILES_DF = pd.DataFrame()

# Initialize paper data
try:
    with data_lock:
        PAPER_JSON_FILES = gcp_ops.load_paper_json_files(PAPERS_JSON_PUBLIC_URL)
        if PAPER_JSON_FILES:
            DIATOMS_DATA = ClaudeAI.get_DIATOMS_DATA(PAPERS_JSON_PUBLIC_URL)
            logger.info(f"Successfully loaded {len(DIATOMS_DATA)} diatom entries")
        else:
            logger.warning("No paper JSON files found")
            PAPER_JSON_FILES = []
            DIATOMS_DATA = []
except Exception as e:
    logger.error(f"Error loading paper data: {str(e)}")
    PAPER_JSON_FILES = []
    DIATOMS_DATA = []

def safe_value(value):
    """Safely handle potentially None values"""
    return value if value else ""

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
    global processing_status, PAPER_JSON_FILES
    TEMP_JSON_FILES = []

    # Construct the papers JSON public URL
    with data_lock:
        PAPER_JSON_FILES = gcp_ops.load_paper_json_files(PAPERS_JSON_PUBLIC_URL) or []

    for i, url in enumerate(pdf_urls, 1):
        with data_lock:
            processing_status['current_index'] = i
            processing_status['current_url'] = url

        try:
            pdf_ops = PDFOps()
            claude = ClaudeAI()

            # Extract text and images
            full_text, first_two_pages_text, filename = pdf_ops.extract_text_from_pdf(url)
            extracted_images_file_metadata = pdf_ops.extract_images_and_metadata(url, SESSION_ID, BUCKET_EXTRACTED_IMAGES)

            # Process the paper
            paper_info, diatoms_data, paper_image_urls = claude.process_paper(full_text, extracted_images_file_metadata)
            citation_info = claude.extract_citation(first_two_pages_text=first_two_pages_text, method="default_citation")

            # Create JSON for the paper
            pdf_paper_json = {
                "pdf_file_url": safe_value(url),
                "filename": safe_value(filename),
                "extracted_images_file_metadata": safe_value(extracted_images_file_metadata),
                "pdf_text_content": safe_value(full_text),
                "first_two_pages_text": safe_value(first_two_pages_text),
                "paper_info": safe_value(paper_info),
                "papers_json_public_url": safe_value(PAPERS_JSON_PUBLIC_URL),
                "diatoms_data": safe_value(diatoms_data),
                "citation": safe_value(citation_info),
            }
            TEMP_JSON_FILES.append(pdf_paper_json)

            with data_lock:
                processing_status.update({
                    'full_text': full_text,
                    'first_two_pages_text': first_two_pages_text,
                    'filename': filename,
                    'citation_info': json.dumps(citation_info, indent=2),
                    'extracted_images_file_metadata': json.dumps(extracted_images_file_metadata, indent=2),
                    'pdf_paper_json': json.dumps(pdf_paper_json, indent=2),
                    'paper_info': json.dumps(paper_info, indent=2),
                    'diatoms_data': json.dumps(diatoms_data, indent=2),
                })
        except Exception as e:
            app.logger.error(f"Error processing PDF at {url}: {str(e)}")
        
        time.sleep(15)  # Simulate processing delay

    # Append TEMP_JSON_FILES to PAPER_JSON_FILES and save
    with data_lock:
        PAPER_JSON_FILES.extend(TEMP_JSON_FILES)
        gcp_ops.save_paper_json_files(PAPERS_JSON_PUBLIC_URL, PAPER_JSON_FILES)

    with data_lock:
        processing_status['complete'] = True


# def process_pdfs(pdf_urls):
#     """Background task to process PDFs"""
#     global processing_status, PAPER_JSON_FILES
    
#     TEMP_JSON_FILES =[]
#     for i, url in enumerate(pdf_urls, 1):
#         processing_status['current_index'] = i
#         processing_status['current_url'] = url
        
#         try:
#             pdf_ops = PDFOps()
#             claude = ClaudeAI()
            
#             papers_json_public_url = f"https://storage.googleapis.com/{PAPERS_BUCKET_JSON_FILES}/jsons_from_pdfs/{SESSION_ID}/{SESSION_ID}.json"
    
#             # Load existing PAPER_JSON_FILES
            
            
#             # Extract text and images
#             full_text, first_two_pages_text, filename = pdf_ops.extract_text_from_pdf(url)
#             extracted_images_file_metadata = pdf_ops.extract_images_and_metadata(url, SESSION_ID, BUCKET_EXTRACTED_IMAGES)
            
#             # Process paper
#             paper_info, diatoms_data, paper_image_urls = claude.process_paper(full_text, extracted_images_file_metadata)
            
#             # Get citation info
#             citation_info = claude.extract_citation(first_two_pages_text=first_two_pages_text, method="default_citation")
            
#             # Create paper JSON
#             pdf_paper_json = {
#                 "pdf_file_url": safe_value(url),
#                 "filename": safe_value(filename),
#                 "extracted_images_file_metadata": safe_value(extracted_images_file_metadata),
#                 "pdf_text_content": safe_value(full_text),
#                 "first_two_pages_text": safe_value(first_two_pages_text),
#                 "paper_info": safe_value(paper_info),
#                 "papers_json_public_url": safe_value(papers_json_public_url),
#                 "diatoms_data": safe_value(diatoms_data),
#                 "citation": safe_value(citation_info)
#             }
            
#             # Update PAPER_JSON_FILES and save
#             # PAPER_JSON_FILES.append(pdf_paper_json)
#             TEMP_JSON_FILES.append(pdf_paper_json)
                  
#             # Update processing status
#             processing_status.update({
#                 'full_text': full_text,
#                 'first_two_pages_text': first_two_pages_text,
#                 'filename': filename,
#                 'citation_info': json.dumps(citation_info, indent=2),
#                 'extracted_images_file_metadata': json.dumps(extracted_images_file_metadata, indent=2),
#                 'pdf_paper_json': json.dumps(pdf_paper_json, indent=2),
#                 'paper_info': json.dumps(paper_info, indent=2),
#                 'diatoms_data': json.dumps(diatoms_data, indent=2)
#             })
            
#         except Exception as e:
#             app.logger.error(f"Error processing PDF: {str(e)}")
#             processing_status.update({
#                 'full_text': 'Error extracting text',
#                 'first_two_pages_text': 'Error extracting text',
#                 'filename': 'Error extracting filename',
#                 'citation_info': 'Error extracting citation',
#                 'extracted_images_file_metadata': 'Error extracting images and file metadata',
#                 'pdf_paper_json': 'Error generating pdf_paper_json',
#                 'paper_info': 'Error generating paper_info',
#                 'diatoms_data': 'Error generating diatoms_data'
#             })
            
#         time.sleep(15)
    
#     processing_status['complete'] = True
#     # Save paper jons to GCP
    
#     PAPER_JSON_FILES = gcp_ops.load_paper_json_files(papers_json_public_url)
#     PAPER_JSON_FILES.extend(TEMP_JSON_FILES)
#     papers_json_public_url = gcp_ops.save_paper_json_files(papers_json_public_url, PAPER_JSON_FILES)

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

#-------------------------------------BOUNDING BOXES---------------------------------------------------------------------------------------

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
    global DIATOMS_DATA
    
    if request.method == 'POST':
        updated_data = request.json
        save_labels(updated_data)
        return jsonify({'success': True})
    
    # Check if we have data before rendering the template
    if not DIATOMS_DATA:
        try:
            # Try to reload the data
            DIATOMS_DATA = ClaudeAI.get_DIATOMS_DATA(PAPERS_JSON_PUBLIC_URL)
        except Exception as e:
            app.logger.error(f"Error loading diatoms data: {str(e)}")
            return render_template('error.html', error="No diatom data available"), 404
    
    # Log the data state
    app.logger.info(f"Label route: Found {len(DIATOMS_DATA)} diatom entries")
    
    return render_template('label-react.html')

# @app.route('/api/diatoms', methods=['GET'])
# def get_diatoms():
#     try:
#         image_index = request.args.get('index', 0, type=int)
        
#         # Use the global DIATOMS_DATA
#         global DIATOMS_DATA
        
#         # Check if we have any data
#         if not DIATOMS_DATA:
#             try:
#                 # Try to reload the data
#                 DIATOMS_DATA = ClaudeAI.get_DIATOMS_DATA(PAPERS_JSON_PUBLIC_URL)
#                 if not DIATOMS_DATA:
#                     return jsonify({
#                         'current_index': 0,
#                         'total_images': 0,
#                         'data': {},
#                         'error': 'No diatoms data available'
#                     })
#             except Exception as e:
#                 app.logger.error(f"Error reloading diatoms data: {str(e)}")
#                 return jsonify({
#                     'current_index': 0,
#                     'total_images': 0,
#                     'data': {},
#                     'error': 'Failed to load diatoms data'
#                 })
        
#         # Ensure index is within bounds
#         total_images = len(DIATOMS_DATA)
#         image_index = min(max(0, image_index), total_images - 1)
        
#         # Log the state
#         app.logger.info(f"Getting diatom data for index {image_index} of {total_images}")
        
#         try:
#             current_image_data = DIATOMS_DATA[image_index]
#             # Log the data being sent
#             app.logger.info(f"Sending image data: {current_image_data.get('image_url', 'No URL')}")
            
#             return jsonify({
#                 'current_index': image_index,
#                 'total_images': total_images,
#                 'data': current_image_data
#             })
#         except IndexError:
#             app.logger.error(f"Failed to get data for index {image_index} from list of length {total_images}")
#             return jsonify({
#                 'current_index': 0,
#                 'total_images': total_images,
#                 'data': {},
#                 'error': 'Invalid image index'
#             })
        
#     except Exception as e:
#         app.logger.error(f"Error in get_diatoms: {str(e)}")
#         return jsonify({
#             'current_index': 0,
#             'total_images': 0,
#             'data': {},
#             'error': f'Error retrieving diatoms data: {str(e)}'
#         }), 500

@app.route('/api/diatoms', methods=['GET'])
def get_diatoms():
    try:
        image_index = request.args.get('index', 0, type=int)
        
        # Use the global DIATOMS_DATA
        global DIATOMS_DATA
        
        # Check if we have any data
        if not DIATOMS_DATA:
            try:
                # Try to reload the data
                DIATOMS_DATA = ClaudeAI.get_DIATOMS_DATA(PAPERS_JSON_PUBLIC_URL)
                if not DIATOMS_DATA:
                    return jsonify({
                        'current_index': 0,
                        'total_images': 0,
                        'data': {},
                        'error': 'No diatoms data available'
                    })
            except Exception as e:
                app.logger.error(f"Error reloading diatoms data: {str(e)}")
                return jsonify({
                    'current_index': 0,
                    'total_images': 0,
                    'data': {},
                    'error': 'Failed to load diatoms data'
                })
        
        # Ensure index is within bounds
        total_images = len(DIATOMS_DATA)
        image_index = min(max(0, image_index), total_images - 1)
        
        try:
            current_image_data = DIATOMS_DATA[image_index]
            
            # Ensure segmentation data is loaded
            if current_image_data.get('segmentation_url') and current_image_data.get('segmentation_indices_array'):
                segmentation_text = gcp_ops.load_segmentation_data(current_image_data['segmentation_url'])
                if segmentation_text:
                    # Process segmentations to add denormalized points
                    current_image_data = segmentation_ops.process_image_segmentations(
                        current_image_data,
                        segmentation_text
                    )
            
            return jsonify({
                'current_index': image_index,
                'total_images': total_images,
                'data': current_image_data
            })
            
        except IndexError:
            app.logger.error(f"Failed to get data for index {image_index} from list of length {total_images}")
            return jsonify({
                'current_index': 0,
                'total_images': total_images,
                'data': {},
                'error': 'Invalid image index'
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
    
#-----------------------------------------SEGMENTATION--------------------------------------------------------------------
 
@app.route('/segmentation')
def segmentation():
    """Route for the segmentation labeling interface"""
    global DIATOMS_DATA
    
    try:
        if not DIATOMS_DATA:
            try:
                DIATOMS_DATA = ClaudeAI.get_DIATOMS_DATA(PAPERS_JSON_PUBLIC_URL)
            except Exception as e:
                app.logger.error("Error loading diatoms data: {}".format(str(e)))
                return render_template('error.html', error="No diatom data available"), 404
        
        # Change this line to send_file instead of render_template
        return send_file('templates/label-segmentation.html', mimetype='text/html')
        
    except Exception as e:
        app.logger.error("Error in segmentation route: {}".format(str(e)))
        return render_template('error.html', error=str(e)), 500

@app.route('/api/save_segmentation', methods=['POST'])
def save_segmentation():
    """Save segmentation data and indices array to GCS bucket and update DIATOMS_DATA"""
    try:
        data = request.json
        image_index = data.get('image_index', 0)
        segmentation_data = data.get('segmentation_data', '')
        image_filename = data.get('image_filename', '')
        segmentation_indices = data.get('segmentation_indices', [])  # Get indices array
        
        logger.info("Saving segmentation for image {}".format(image_filename))
        logger.debug("Segmentation data: {}".format(segmentation_data))
        logger.debug("Segmentation indices: {}".format(segmentation_indices))
        
        if not segmentation_data or not image_filename:
            raise ValueError("Missing required data")
            
        # Save segmentation data to GCS bucket
        segmentation_url = gcp_ops.save_segmentation_data(
            segmentation_data=segmentation_data,
            image_filename=image_filename,
            session_id=SESSION_ID,
            bucket_name=BUCKET_SEGMENTATION_LABELS
        )
        
        if not segmentation_url:
            raise Exception("Failed to save segmentation data to GCS")
        
        logger.info("Saved segmentation to URL: {}".format(segmentation_url))
            
        # Update DIATOMS_DATA with both the segmentation URL and indices array
        if 0 <= image_index < len(DIATOMS_DATA):
            DIATOMS_DATA[image_index]['segmentation_url'] = segmentation_url
            DIATOMS_DATA[image_index]['segmentation_indices_array'] = segmentation_indices
            
            # Update corresponding entry in PAPER_JSON_FILES
            for paper in PAPER_JSON_FILES:
                if 'diatoms_data' in paper:
                    if isinstance(paper['diatoms_data'], str):
                        paper['diatoms_data'] = json.loads(paper['diatoms_data'])
                    
                    if paper['diatoms_data'].get('image_url') == DIATOMS_DATA[image_index].get('image_url'):
                        paper['diatoms_data']['segmentation_url'] = segmentation_url
                        paper['diatoms_data']['segmentation_indices_array'] = segmentation_indices
                        break
            
            # Save updated data to GCS
            success = ClaudeAI.update_and_save_papers(
                PAPERS_JSON_PUBLIC_URL,
                PAPER_JSON_FILES,
                DIATOMS_DATA
            )
            
            if not success:
                raise Exception("Failed to update papers data in GCS")
                
            return jsonify({
                'success': True,
                'message': 'Segmentation saved successfully',
                'segmentation_url': segmentation_url,
                'segmentation_indices_array': segmentation_indices
            })
        else:
            raise ValueError("Invalid image index: {}".format(image_index))
            
    except Exception as e:
        logger.error("Error saving segmentation: {}".format(str(e)))
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/get_segmentation')
def get_segmentation():
    """Proxy route to fetch segmentation annotations and indices from GCS"""
    try:
        url = request.args.get('url')
        image_index = request.args.get('image_index', type=int)
        
        if not url:
            raise ValueError("No URL provided")
            
        logger.info(f"Attempting to load segmentation annotations from: {url}")
        
        # Use the existing load_segmentation_data method but store as annotations
        annotations = gcp_ops.load_segmentation_data(url)
        
        if annotations is None:
            logger.error(f"No segmentation annotations found at {url}")
            return jsonify({'error': 'Segmentation annotations not found'}), 404
        
        # Get the segmentation indices array from DIATOMS_DATA
        segmentation_indices = None
        if image_index is not None and 0 <= image_index < len(DIATOMS_DATA):
            segmentation_indices = DIATOMS_DATA[image_index].get('segmentation_indices_array')
            
        logger.info(f"Successfully loaded segmentation annotations: {len(annotations)} characters")
        logger.info(f"Segmentation indices: {segmentation_indices}")
        
        return jsonify({
            'annotations': annotations,
            'segmentation_indices_array': segmentation_indices
        }), 200
        
    except Exception as e:
        logger.error(f"Error in get_segmentation: {str(e)}")
        return jsonify({
            'error': f"Failed to fetch segmentation annotations: {str(e)}"
        }), 500
        
@app.route('/api/download_segmentation')
def download_segmentation():
    """Download all segmentation data for current session"""
    try:
        # Create a temporary file containing all segmentation data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            segmentation_data = [{
                'image_url': item.get('image_url', ''),
                'segmentation_url': item.get('segmentation_url', ''),
                'image_width': item.get('image_width', ''),
                'image_height': item.get('image_height', '')
            } for item in DIATOMS_DATA if item.get('segmentation_url')]
            
            json.dump(segmentation_data, temp_file, indent=4)
            temp_path = temp_file.name
        
        try:
            response = send_file(
                temp_path,
                mimetype='application/json',
                as_attachment=True,
                download_name=f'segmentation_data_{SESSION_ID}.json'
            )
            os.unlink(temp_path)
            return response
        except Exception as e:
            os.unlink(temp_path)
            raise e
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


#-------------------------------------------------------------------------------------------------------------
@app.route('/json')
def display_json():
    return render_template('displayjson.html')

#--------------------------UPLOAD PDF FILES---------------------------------------------------------------------
@app.route('/view_pdf/<path:blob_name>')
def view_pdf(blob_name):
    try:
        # Download the PDF content
        content = gcp_ops.get_blob_content(PAPERS_BUCKET, blob_name)
        
        # Return the PDF in an inline content disposition
        return Response(
            content,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': 'inline; filename=' + blob_name.split('/')[-1]
            }
        )
    except Exception as e:
        flash(f'Error viewing PDF: {str(e)}')
        return redirect(url_for('upload_file'))

@app.route('/preview_pdf/<path:blob_name>')
def preview_pdf(blob_name):
    """Render a page to preview the PDF"""
    return render_template('pdf_viewer.html', pdf_url=url_for('view_pdf', blob_name=blob_name))

def ensure_clean_temp_dir(tmp_dir):
    """
    Ensures a clean temporary directory exists.
    If it exists, removes it and recreates it.
    If it doesn't exist, creates it.
    """
    if os.path.exists(tmp_dir):
        try:
            shutil.rmtree(tmp_dir)
        except Exception as e:
            print(f"Error cleaning temporary directory: {e}")
            # If we can't remove it, try to work with existing directory
            return
    
    try:
        os.makedirs(tmp_dir)
    except Exception as e:
        print(f"Error creating temporary directory: {e}")
        raise

# @app.route('/upload_pdfs', methods=['GET', 'POST'])
# def upload_file():
#     if request.method == 'POST':
#         if 'files[]' not in request.files:
#             flash('No files selected')
#             return redirect(request.url)
        
#         files = request.files.getlist('files[]')
        
#         if not files or all(file.filename == '' for file in files):
#             flash('No files selected')
#             return redirect(request.url)
        
#         upload_count = 0
#         error_count = 0
        
#         # Ensure base upload folder exists
#         os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
#         # Create a clean temporary directory for this session
#         TMP_DIR = os.path.join(app.config['UPLOAD_FOLDER'], SESSION_ID)
#         try:
#             ensure_clean_temp_dir(TMP_DIR)
#         except Exception as e:
#             flash('Error preparing upload directory')
#             print(f"Directory preparation error: {e}")
#             return redirect(request.url)
        
#         for file in files:
#             if file and allowed_file(file.filename):
#                 filename = secure_filename(file.filename)
#                 temp_path = os.path.join(TMP_DIR, filename)
                
#                 try:
#                     file.save(temp_path)
#                     blob_name, public_url = gcp_ops.save_pdf_file_to_bucket(
#                         temp_path, 
#                         PAPERS_BUCKET, 
#                         SESSION_ID
#                     )
                    
#                     if blob_name:
#                         upload_count += 1
#                     else:
#                         error_count += 1
                        
#                 except Exception as e:
#                     print(f"Error processing file {filename}: {e}")
#                     error_count += 1
#                 finally:
#                     # Clean up temporary file regardless of success/failure
#                     if os.path.exists(temp_path):
#                         try:
#                             os.remove(temp_path)
#                         except Exception as e:
#                             print(f"Error removing temporary file {temp_path}: {e}")
#             else:
#                 error_count += 1
        
#         # Clean up the temporary directory after all files are processed
#         try:
#             shutil.rmtree(TMP_DIR)
#         except Exception as e:
#             print(f"Error removing temporary directory {TMP_DIR}: {e}")
        
#         if upload_count > 0:
#             flash(f'Successfully uploaded {upload_count} file(s)')
#         if error_count > 0:
#             flash(f'Failed to upload {error_count} file(s)')
        
#         return redirect(url_for('upload_file'))

#     # GET request handling
#     files = gcp_ops.get_uploaded_files(PAPERS_BUCKET, SESSION_ID)
#     return render_template('upload_images.html', files=files)

@app.route('/upload_pdfs', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'files[]' not in request.files:
            flash('No files selected')
            return redirect(request.url)
        
        files = request.files.getlist('files[]')
        
        if not files or all(file.filename == '' for file in files):
            flash('No files selected')
            return redirect(request.url)
        
        # Create upload directory if it doesn't exist
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        TMP_DIR = os.path.join(app.config['UPLOAD_FOLDER'], SESSION_ID)
        os.makedirs(TMP_DIR, exist_ok=True)
        
        upload_count = 0
        error_count = 0
        skipped_files = []
        current_size = 0
        MAX_BATCH_SIZE = 60 * 1024 * 1024  # Leave some buffer below the 64MB limit
        
        # Process files while tracking total size
        for file in files:
            if file and allowed_file(file.filename):
                # Get file size from FileStorage object
                file.seek(0, 2)  # Seek to end
                file_size = file.tell()
                file.seek(0)  # Reset to beginning
                
                # Skip this file if it would exceed our batch size
                if current_size + file_size > MAX_BATCH_SIZE:
                    skipped_files.append(file.filename)
                    continue
                
                current_size += file_size
                filename = secure_filename(file.filename)
                temp_path = os.path.join(TMP_DIR, filename)
                
                try:
                    file.save(temp_path)
                    blob_name, public_url = gcp_ops.save_pdf_file_to_bucket(temp_path, PAPERS_BUCKET, SESSION_ID)
                    
                    if blob_name:
                        upload_count += 1
                    else:
                        error_count += 1
                        
                except Exception as e:
                    print(f"Error processing file {filename}: {e}")
                    error_count += 1
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            else:
                error_count += 1
        
        # Clean up temporary directory
        try:
            os.rmdir(TMP_DIR)  # Only removes if empty
        except Exception as e:
            print(f"Error removing temporary directory: {e}")
        
        # Provide feedback about uploaded and skipped files
        if upload_count > 0:
            flash(f'Successfully uploaded {upload_count} file(s)')
        if error_count > 0:
            flash(f'Failed to upload {error_count} file(s)')
        if skipped_files:
            skipped_msg = 'Please retry uploading these files separately: ' + ', '.join(skipped_files)
            flash(skipped_msg)
        
        return redirect(url_for('upload_file'))

    files = gcp_ops.get_uploaded_files(PAPERS_BUCKET, SESSION_ID)
    return render_template('upload_images.html', files=files)


#---------------------------------------------------------------------------------------------
#--------------------------------------- COLOSUS----------------------------------------------
def fetch_and_process_data():
    """Fetch data from the CSV URL and properly convert synonyms to string"""
    url = "https://storage.googleapis.com/papers-diatoms-colossus/cvs/colossus.csv"
    try:
        df = pd.read_csv(url)
        # Convert the synonyms column data type to string without splitting characters
        df['synonyms'] = df['synonyms'].str.join('')
        return df.to_dict('records')
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []

@app.route('/colosus')
def display_table():
    """Route to display the auto-refreshing table"""
    data = fetch_and_process_data()
    return render_template('colosus.html', data=data)

#-----------------------------------------------------------------------------------------------
#------------------------------Diatom List Assistant-------------------------------------------
# The list assistant retrieves the missing diatom species and adds them to diatoms_data for the image
# @app.route('/api/diatom_list_assistant', methods=['GET'])
# def get_diatom_list_assistant():
#     try:
#         image_index = request.args.get('index', 0, type=int)
        
#         if not DIATOMS_DATA or image_index >= len(DIATOMS_DATA):
#             return jsonify({
#                 'error': 'No data available or invalid index'
#             }), 404

#         # Get the current image data
#         current_image_data = DIATOMS_DATA[image_index]
        
#         # Extract labels from the info array
#         labels = [info['label'][0] for info in current_image_data.get('info', [])]
        
#         # Find corresponding paper in PAPER_JSON_FILES
#         pdf_text_content = ""
#         for paper in PAPER_JSON_FILES:
#             if isinstance(paper.get('diatoms_data'), str):
#                 paper_diatoms_data = json.loads(paper['diatoms_data'])
#             else:
#                 paper_diatoms_data = paper.get('diatoms_data', {})
                
#             if paper_diatoms_data.get('image_url') == current_image_data.get('image_url'):
#                 pdf_text_content = paper.get('pdf_text_content', '')
#                 break
        
#         return jsonify({
#             'labels': labels,
#             'pdf_text_content': pdf_text_content
#         })
        
#     except Exception as e:
#         app.logger.error(f"Error in get_diatom_list_assistant: {str(e)}")
#         return jsonify({
#             'error': f'Error retrieving diatom list assistant data: {str(e)}'
#         }), 500



@app.route('/api/diatom_list_assistant', methods=['GET'])
def get_diatom_list_assistant():
    try:
        image_index = request.args.get('index', 0, type=int)
        
        if not DIATOMS_DATA or image_index >= len(DIATOMS_DATA):
            return jsonify({
                'error': 'No data available or invalid index'
            }), 404

        # Get the current image data
        current_image_data = DIATOMS_DATA[image_index]
        
        # Extract existing labels from the info array
        labels = [info['label'][0] for info in current_image_data.get('info', [])]
        
        
        # Find corresponding paper and pdf_text_content
        pdf_text_content = ""
        matching_paper = None
        for paper in PAPER_JSON_FILES:
            if isinstance(paper.get('diatoms_data'), str):
                paper_diatoms_data = json.loads(paper['diatoms_data'])
            else:
                paper_diatoms_data = paper.get('diatoms_data', {})
                
            if paper_diatoms_data.get('image_url') == current_image_data.get('image_url'):
                pdf_text_content = paper.get('pdf_text_content', '')
                matching_paper = paper
                break
            
                

        # Use Claude to find missing species
        claude = ClaudeAI()
        reformatted_labels = claude.reformat_labels_to_spaces(labels)
        # messages = claude.part3_create_missing_species_prompt_and_messages(pdf_text_content, labels)
        messages = claude.part3_create_missing_species_prompt_and_messages(pdf_text_content, reformatted_labels)
        response = claude.get_completion(messages)

        if "error" in response:
            return jsonify({
                'error': 'Failed to process text with Claude',
                'details': response["error"]
            }), 500

        if not isinstance(response, dict):
            return jsonify({
                'error': 'Invalid response format from Claude',
                'details': 'Expected dictionary, got ' + str(type(response))
            }), 500

        # Validate response has required fields
        required_fields = ['species_data', 'labels_retrieved', 'message']
        missing_fields = [field for field in required_fields if field not in response]
        if missing_fields:
            return jsonify({
                'error': 'Missing required fields in Claude response',
                'details': f"Missing fields: {', '.join(missing_fields)}"
            }), 500

        # Add new species to current_image_data's info array
        new_species_added = False
        if response['species_data']:
            current_image_data['info'].extend(response['species_data'])
            new_species_added = True

            # Update the matching paper's diatoms_data
            if matching_paper:
                if isinstance(matching_paper['diatoms_data'], str):
                    matching_paper['diatoms_data'] = json.loads(matching_paper['diatoms_data'])
                matching_paper['diatoms_data'] = current_image_data

                # Save updated data to GCP
                success = ClaudeAI.update_and_save_papers(
                    PAPERS_JSON_PUBLIC_URL,
                    PAPER_JSON_FILES,
                    DIATOMS_DATA
                )
                if not success:
                    logger.error("Failed to save updated data to GCP")

        # Return the complete data for frontend processing
        return jsonify({
            'labels': labels,
            'pdf_text_content': pdf_text_content,
            'species_data': response.get('species_data', []),
            'labels_retrieved': response.get('labels_retrieved', []),
            'message': response.get('message', ''),
            'data_saved': new_species_added
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error in diatom_list_assistant: {str(e)}")
        return jsonify({
            'error': 'Failed to parse JSON response',
            'details': str(e)
        }), 500
    except Exception as e:
        logger.error(f"Error in diatom_list_assistant: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

#--------------------------------------------Label Union ------------------------------------------------

# Add these routes to your app.py
@app.route('/label_union')
def label_union():
    """Route for the label union interface"""
    global DIATOMS_DATA
    
    try:
        if not DIATOMS_DATA:
            try:
                DIATOMS_DATA = ClaudeAI.get_DIATOMS_DATA(PAPERS_JSON_PUBLIC_URL)
            except Exception as e:
                app.logger.error(f"Error loading diatoms data: {str(e)}")
                return render_template('error.html', error="No diatom data available"), 404
        
        return send_file('templates/label-union.html', mimetype='text/html')
        
    except Exception as e:
        app.logger.error(f"Error in label_union route: {str(e)}")
        return render_template('error.html', error=str(e)), 500

# @app.route('/api/align_bbox_segmentation', methods=['POST'])
# def align_bbox_segmentation():
#     """Align bounding boxes with segmentations for a single image"""
#     try:
#         data = request.json
#         image_index = data.get('image_index', 0)
        
#         if not 0 <= image_index < len(DIATOMS_DATA):
#             raise ValueError("Invalid image index")

#         current_image_data = DIATOMS_DATA[image_index]
        
#         # Verify segmentation URL exists
#         if not current_image_data.get('segmentation_url'):
#             return jsonify({
#                 'success': False,
#                 'error': 'No segmentation data available'
#             }), 400
            
#         # Load segmentation data
#         segmentation_text = gcp_ops.load_segmentation_data(current_image_data['segmentation_url'])
#         if not segmentation_text:
#             return jsonify({
#                 'success': False,
#                 'error': 'Failed to load segmentation data'
#             }), 400
            
#         # Process segmentations
#         updated_image_data = segmentation_ops.process_image_segmentations(
#             current_image_data,
#             segmentation_text
#         )
        
#         # Validate results
#         if not updated_image_data.get('segmentation_indices_array'):
#             return jsonify({
#                 'success': False,
#                 'error': 'Failed to process segmentations'
#             }), 500
        
#         # Update DIATOMS_DATA
#         DIATOMS_DATA[image_index] = updated_image_data
        
#         # Update paper JSON files
#         updated_paper = False
#         for paper in PAPER_JSON_FILES:
#             if isinstance(paper.get('diatoms_data'), str):
#                 paper['diatoms_data'] = json.loads(paper['diatoms_data'])
            
#             if paper['diatoms_data'].get('image_url') == current_image_data.get('image_url'):
#                 paper['diatoms_data'] = updated_image_data
#                 updated_paper = True
#                 break
        
#         if not updated_paper:
#             app.logger.warning(f"No matching paper found for image {image_index}")
        
#         # Save to GCP
#         success = ClaudeAI.update_and_save_papers(
#             PAPERS_JSON_PUBLIC_URL,
#             PAPER_JSON_FILES,
#             DIATOMS_DATA
#         )
        
#         if not success:
#             raise Exception("Failed to save updates to GCP")
        
#         return jsonify({
#             'success': True,
#             'message': 'Alignment saved successfully',
#             'updated_data': updated_image_data
#         })
        
#     except Exception as e:
#         app.logger.error(f"Error in align_bbox_segmentation: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

@app.route('/api/align_bbox_segmentation', methods=['POST'])
def align_bbox_segmentation():
    """Align bounding boxes with segmentations for a single image"""
    try:
        data = request.json
        image_index = data.get('image_index', 0)
        
        if not 0 <= image_index < len(DIATOMS_DATA):
            raise ValueError("Invalid image index")

        current_image_data = DIATOMS_DATA[image_index]
        
        # Verify segmentation URL exists
        if not current_image_data.get('segmentation_url'):
            return jsonify({
                'success': False,
                'error': 'No segmentation data available'
            }), 400
            
        # Load segmentation data
        segmentation_text = gcp_ops.load_segmentation_data(current_image_data['segmentation_url'])
        if not segmentation_text:
            return jsonify({
                'success': False,
                'error': 'Failed to load segmentation data'
            }), 400
            
        # Process segmentations
        updated_image_data = segmentation_ops.process_image_segmentations(
            current_image_data,
            segmentation_text
        )
        
        # Update DIATOMS_DATA
        DIATOMS_DATA[image_index] = updated_image_data
        
        # Update paper JSON files
        updated_paper = False
        for paper in PAPER_JSON_FILES:
            if isinstance(paper.get('diatoms_data'), str):
                paper['diatoms_data'] = json.loads(paper['diatoms_data'])
            
            if paper['diatoms_data'].get('image_url') == current_image_data.get('image_url'):
                paper['diatoms_data'] = updated_image_data
                updated_paper = True
                break
        
        if not updated_paper:
            app.logger.warning(f"No matching paper found for image {image_index}")
        
        # Save to GCP
        success = ClaudeAI.update_and_save_papers(
            PAPERS_JSON_PUBLIC_URL,
            PAPER_JSON_FILES,
            DIATOMS_DATA
        )
        
        if not success:
            raise Exception("Failed to save updates to GCP")
        
        return jsonify({
            'success': True,
            'message': 'Alignment saved successfully',
            'updated_data': updated_image_data
        })
        
    except Exception as e:
        app.logger.error(f"Error in align_bbox_segmentation: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
        
        
@app.route('/api/align_all_images', methods=['POST'])
def align_all_images():
    """Automatically align bounding boxes with segmentations for all images"""
    try:
        total_processed = 0
        errors = []
        processed_indices = []
        
        for index, image_data in enumerate(DIATOMS_DATA):
            try:
                # Skip images without segmentation data
                if not image_data.get('segmentation_url'):
                    continue
                    
                # Load segmentation data
                segmentation_text = gcp_ops.load_segmentation_data(image_data['segmentation_url'])
                if not segmentation_text:
                    errors.append(f"Failed to load segmentation data for image {index}")
                    continue
                
                # Process segmentations
                updated_image_data = segmentation_ops.process_image_segmentations(
                    image_data,
                    segmentation_text
                )
                
                if not updated_image_data.get('segmentation_indices_array'):
                    errors.append(f"Failed to process segmentations for image {index}")
                    continue
                
                # Update DIATOMS_DATA
                DIATOMS_DATA[index] = updated_image_data
                
                # Update corresponding paper
                for paper in PAPER_JSON_FILES:
                    if isinstance(paper.get('diatoms_data'), str):
                        paper['diatoms_data'] = json.loads(paper['diatoms_data'])
                    
                    if paper['diatoms_data'].get('image_url') == image_data.get('image_url'):
                        paper['diatoms_data'] = updated_image_data
                        break
                
                total_processed += 1
                processed_indices.append(index)
                
            except Exception as e:
                errors.append(f"Error processing image {index}: {str(e)}")
                continue
        
        # Save all updates to GCP
        if total_processed > 0:
            success = ClaudeAI.update_and_save_papers(
                PAPERS_JSON_PUBLIC_URL,
                PAPER_JSON_FILES,
                DIATOMS_DATA
            )
            
            if not success:
                raise Exception("Failed to save updates to GCP")
        
        return jsonify({
            'success': True,
            'total_processed': total_processed,
            'processed_indices': processed_indices,
            'errors': errors,
            'message': f'Successfully processed {total_processed} images'
        })
        
    except Exception as e:
        app.logger.error(f"Error in align_all_images: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ----------------------------------------------------------------------------------------


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, threaded=True)