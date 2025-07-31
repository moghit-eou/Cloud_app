#!/usr/bin/env python3

from flask import Flask, request, redirect, session, render_template_string, url_for
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import os
import json
import requests
from urllib.parse import parse_qs, urlparse

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

app = Flask(__name__)
app.secret_key = os.urandom(24)

CLIENT_SECRETS_FILE = "credentials.json"
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def credentials_to_dict(credentials):
    print("\n\n ___________function credentials_to_dict called______________\n\n")
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

def get_flow():
    print("function get_flow called")
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES)
    flow.redirect_uri = url_for('oauth_callback', _external=True)
    flow.oauth2session.scope = SCOPES
    return flow

@app.route('/')
def index():
    print("\n\n ____________function index called______________ \n\n")
    if 'credentials' not in session:
        return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Google Drive File Lister</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 50px; }
                .btn { background: #4285f4; color: white; padding: 15px 30px; 
                       text-decoration: none; border-radius: 5px; display: inline-block; }
                .btn:hover { background: #3367d6; }
            </style>
        </head>
        <body>
            <h1> Google Drive File Lister</h1>
            <p>This web application will list files from your Google Drive.</p>
            <a href="{{ url_for('authorize') }}" class="btn"> Login with Google</a>
        </body>
        </html>
        ''')
    else:
        return redirect(url_for('list_files'))

@app.route('/authorize')
def authorize():
    print("\n\n____________function authorize called______________\n\n")
    flow = get_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth_callback')
def oauth_callback():
    print("\n\n")
    print("____________function oauth_callback called______________")
    print("\n\n")
    stored_state = session.pop('state', None)
    received_state = request.args.get('state')
    
    if not stored_state or stored_state != received_state:
        session.clear()
        return redirect(url_for('index'))
    
    flow = get_flow()
    
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            flow.fetch_token(authorization_response=request.url)
    except Exception as e:
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, scopes=SCOPES)
        flow.redirect_uri = url_for('oauth_callback', _external=True)
        
        parsed_url = urlparse(request.url)
        auth_code = parse_qs(parsed_url.query).get('code', [None])[0]
        
        if auth_code:
            token_url = "https://oauth2.googleapis.com/token"
            
            with open(CLIENT_SECRETS_FILE, 'r') as f:
                client_config = json.load(f)['web']
            
            token_data = {
                'client_id': client_config['client_id'],
                'client_secret': client_config['client_secret'],
                'redirect_uri': flow.redirect_uri,
                'grant_type': 'authorization_code',
                'code': auth_code
            }
            
            response = requests.post(token_url, data=token_data)
            token_info = response.json()
            
            if 'access_token' in token_info:
                credentials = google.oauth2.credentials.Credentials(
                    token=token_info['access_token'],
                    refresh_token=token_info.get('refresh_token'),
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=client_config['client_id'],
                    client_secret=client_config['client_secret'],
                    scopes=SCOPES
                )
                
                session['credentials'] = credentials_to_dict(credentials)
                return redirect(url_for('list_files'))
        
        return f'Authentication failed: {str(e)}', 400
    
    credentials = flow.credentials
    session['credentials'] = credentials_to_dict(credentials)
    
    return redirect(url_for('list_files'))

@app.route('/files')
def list_files():
    print("\n\n")
    print("____________function list_files called______________")
    print("\n\n")

    
    if 'credentials' not in session:
        return redirect(url_for('index'))
    
    credentials = google.oauth2.credentials.Credentials(**session['credentials'])
    service = googleapiclient.discovery.build('drive', 'v3', credentials=credentials)
    
    try:
        results = service.files().list(
            pageSize=20,
            fields="files(name, mimeType, size, modifiedTime, id)"
        ).execute()
        
        files = results.get('files', [])
        
        html_content = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Your Google Drive Files</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 30px; }
                .file { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }
                .file-name { font-size: 18px; font-weight: bold; color: #1a73e8; }
                .file-details { color: #666; margin-top: 5px; }
                .logout { background: #ea4335; color: white; padding: 10px 20px; 
                         text-decoration: none; border-radius: 5px; float: right; }
                .logout:hover { background: #d93025; }
                h1 { color: #333; }
            </style>
        </head>
        <body>
            <h1> Your Google Drive Files</h1>
            <a href="{{ url_for('logout') }}" class="logout"> Logout</a>
            <div style="clear: both; margin-bottom: 30px;"></div>
        '''
        
        if not files:
            html_content += '<p>No files found in your Google Drive.</p>'
        else:
            html_content += f'<p>Found <strong>{len(files)}</strong> files:</p>'
            
            for i, file in enumerate(files, 1):
                name = file['name']
                file_type = file.get('mimeType', 'Unknown type')
                size = file.get('size', 'N/A')
                modified = file.get('modifiedTime', 'Unknown')
                
                if size != 'N/A':
                    size_mb = int(size) / (1024 * 1024)
                    size = f"{size_mb:.2f} MB"
                
                if 'google-apps' in file_type:
                    if 'document' in file_type:
                        file_type = 'Google Doc'
                    elif 'spreadsheet' in file_type:
                        file_type = 'Google Sheet'
                    elif 'presentation' in file_type:
                        file_type = 'Google Slides'
                    elif 'folder' in file_type:
                        file_type = 'Folder'
                    else:
                        file_type = 'Google Workspace file'
                
                html_content += f'''
                <div class="file">
                    <div class="file-name">{i}. {name}</div>
                    <div class="file-details">
                        <strong>Type:</strong> {file_type}<br>
                        <strong>Size:</strong> {size}<br>
                        <strong>Modified:</strong> {modified[:10] if modified != 'Unknown' else 'Unknown'}
                    </div>
                </div>
                '''
        
        html_content += '''
            </body>
            </html>
        '''
        
        return render_template_string(html_content)
        
    except Exception as e:
        return f'<h1>Error accessing Google Drive</h1><p>{str(e)}</p><a href="/">Go back</a>'

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    if not os.path.exists(CLIENT_SECRETS_FILE):
        exit(1)
    app.run(debug=True, host='localhost', port=5000)
