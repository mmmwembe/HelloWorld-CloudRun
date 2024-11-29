# app.py
from flask import Flask, render_template, send_file
import os
from modules.installed_packages import get_installed_packages
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World!'


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
    file_path = os.path.join("temp_uploads", filename)
    os.makedirs("temp_uploads", exist_ok=True)
    
    # Write the data to the file
    with open(file_path, 'w') as file:
        file.write(formatted_data)
    
    # Return the file for download
    return send_file(file_path, as_attachment=True)




if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)