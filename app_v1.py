from flask import Flask, render_template, send_file
import os
from datetime import datetime
from modules.installed_packages import get_installed_packages
from modules import ClaudeAI

app = Flask(__name__)

# Constants
SESSION_ID = 'eb9db0ca54e94dbc82cffdab497cde13'
PAPERS_BUCKET = 'papers-diatoms'

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
        return render_template('papers.html', pdf_urls=pdf_urls, num_papers = len(pdf_urls))
    except Exception as e:
        # Log the error for debugging
        print(f"Error in /all_papers: {str(e)}")
        # Render template with error message
        return render_template('papers.html', 
                             pdf_urls=[], 
                             error=f"Unable to retrieve papers: {str(e)}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)