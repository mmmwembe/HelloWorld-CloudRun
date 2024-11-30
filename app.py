from flask import Flask, render_template, send_file, request, jsonify, redirect, url_for, flash, send_from_directory
import os
from datetime import datetime
import time
import json
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

def safe_value(value):
    return value if value else ""

# Create an instance of GCPOps
gcp_ops = GCPOps()

# Call the method with the new variable name
UPLOADED_PDF_FILES_DF = gcp_ops.initialize_paper_upload_tracker_df_from_gcp(
    session_id=SESSION_ID,
    bucket_name=BUCKET_PAPER_TRACKER_CSV
)

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
            part1_prompt = claude.part1_create_paper_info_json_from_pdf_text_content_prompt()
            part1_messages = claude.part1_create_messages_for_paper_info_json(full_text, part1_prompt)
            paper_info = claude.get_completion(part1_messages)
            time.sleep(10)
            
            paper_image_urls = paper_info.get("paper_image_urls", [])
            # part2_prompt = claude.part2_create_diatoms_data_object_for_paper()
            # part2_messages =claude.part2_create_messages_for_diatoms_data_object_creation(paper_info, paper_image_urls, part2_prompt)
            # paper_diatoms_data = claude.get_completion(part2_messages)
            
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
                "diatoms_data": safe_value(paper_image_urls),
                "citation": safe_value(citation_info)
            }
            
            
            # Update processing status with new information
            processing_status['full_text'] = full_text
            processing_status['first_two_pages_text'] = first_two_pages_text
            processing_status['filename'] = filename
            processing_status['citation_info'] = json.dumps(citation_info, indent=2)
            processing_status['extracted_images_file_metadata'] = json.dumps(extracted_images_file_metadata, indent=2)
            processing_status['pdf_paper_json'] = json.dumps(pdf_paper_json, indent=2)            
            processing_status['paper_info'] = json.dumps(paper_info, indent=2)                
            processing_status['diatoms_data'] = paper_image_urls  
                        
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
        time.sleep(10)
    
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








if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, threaded=True)