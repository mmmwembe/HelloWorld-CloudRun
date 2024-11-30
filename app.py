from flask import Flask, render_template, send_file, request, jsonify, redirect, url_for, flash
import os
from datetime import datetime
import time
import json
from threading import Thread
from modules.installed_packages import get_installed_packages
from modules import ClaudeAI
from modules import GCPOps

app = Flask(__name__)

# Constants
SESSION_ID = 'eb9db0ca54e94dbc82cffdab497cde13'
PAPERS_BUCKET = 'papers-diatoms'
PAPERS_PROCESSED_BUCKET ='papers-diatoms-processed'
PAPERS_BUCKET_LABELLING ='papers-diatoms-labelling'
PAPERS_BUCKET_JSON_FILES ='papers-diatoms-jsons'
BUCKET_EXTRACTED_IMAGES = 'papers-extracted-images-bucket-mmm'
BUCKET_PAPER_TRACKER_CSV = 'papers-extracted-pages-csv-bucket-mmm'


# Create an instance of GCPOps
gcp_ops = GCPOps()

# Call the method with the new variable name
UPLOADED_PDF_FILES_DF = gcp_ops.initialize_paper_upload_tracker_df_from_gcp(
    session_id=SESSION_ID,
    bucket_name=BUCKET_PAPER_TRACKER_CSV
)


# Global variables for tracking processing status
processing_status = {
    'current_index': 0,
    'current_url': '',
    'complete': False,
    'total_pdfs': 0
}

def process_pdfs(pdf_urls):
    """Background task to process PDFs"""
    global processing_status
    
    for i, url in enumerate(pdf_urls, 1):
        processing_status['current_index'] = i
        processing_status['current_url'] = url
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



@app.route('/view_uploaded_pdfs')
def view_uploaded_pdfs():
    try:
        return send_file('templates/view_uploaded_pdfs.html')
    except Exception as e:
        flash(f'Error loading PDF viewer: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/api/pdf_data')
def get_pdf_data():
    try:
        # Convert DataFrame to dictionary format
        pdf_data = UPLOADED_PDF_FILES_DF.to_dict(orient='records')
        return jsonify(pdf_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500








if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, threaded=True)