from flask import Flask, request, redirect, session, url_for, render_template_string , render_template , session , jsonify
import os
import json
import google_auth_oauthlib.flow
import google.oauth2.credentials
import googleapiclient.discovery
from googleapiclient.http import MediaFileUpload
from io import BytesIO
from flask import send_file



os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

app = Flask(__name__)
app.secret_key = os.urandom(24)

CLIENT_SECRETS_FILE = "credentials.json"
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_flow():
    print("\n\n ___________function get_flow called______________\n\n")
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES)
    flow.redirect_uri = url_for('oauth_callback', _external=True)
    return flow

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
def get_service():
    creds = google.oauth2.credentials.Credentials(**session['credentials'])
    return googleapiclient.discovery.build('drive', 'v3', credentials=creds)
 

def get_folder_path(service, file_id, folder_cache={}):
    """Get the full path of a file/folder by traversing parent folders"""
    if file_id in folder_cache:
        return folder_cache[file_id]
    
    try:
        file_meta = service.files().get(fileId=file_id, fields='name,parents').execute()
        file_name = file_meta.get('name', '')
        parents = file_meta.get('parents', [])
        
        if not parents:
            folder_cache[file_id] = file_name
            return file_name
        
        parent_path = get_folder_path(service, parents[0], folder_cache)
        full_path = f"{parent_path}/{file_name}" if parent_path else file_name
        folder_cache[file_id] = full_path
        return full_path
    except:
        return "Unknown"



@app.route('/')
def index():
    print("\n\n ____________function index called______________ \n\n")
    if 'credentials' not in session:
        return render_template('login.html')

    return redirect(url_for('home_page'))

@app.route('/authorize')
def authorize():
    print("\n\n____________function authorize called______________\n\n")
    flow = get_flow()
    auth_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    session['state'] = state
    return redirect(auth_url)


@app.route('/oauth_callback')
def oauth_callback():
    print("\n\n____________function oauth_callback called______________\n\n")
    flow = get_flow()
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session['credentials'] = credentials_to_dict(credentials)
    return redirect(url_for('home_page'))


@app.route('/search')
def search():
    """Real-time search endpoint"""
    if 'credentials' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    
    try:
        service = get_service()
        
        # Search for files and folders that contain the query in their name
        search_query = f"name contains '{query}' and trashed=false"
        
        results = service.files().list(
            q=search_query,
            pageSize=20,
            fields="files(id,name,mimeType,parents,webViewLink)"
        ).execute()
        
        files = results.get('files', [])
        suggestions = []
        
        for file in files:
            # Get the full path for each file/folder
            full_path = get_folder_path(service, file['id'])
            
            # Determine if it's a folder or file
            is_folder = file['mimeType'] == 'application/vnd.google-apps.folder'
            
            suggestions.append({
                'id': file['id'],
                'name': file['name'],
                'path': full_path,
                'type': 'folder' if is_folder else 'file',
                'webViewLink': file.get('webViewLink', ''),
                'downloadLink': url_for('download_file', file_id=file['id']) if not is_folder else None,
                'deleteLink': url_for('delete_file', file_id=file['id'])
            })
        
        # Sort by relevance (exact matches first, then by name)
        suggestions.sort(key=lambda x: (
            not x['name'].lower().startswith(query.lower()),
            x['name'].lower()
        ))
        
        return jsonify(suggestions)
    
    except Exception as e:
        print(f"Search error: {e}")
        return jsonify({'error': 'Search failed'}), 500

@app.route('/home', defaults={'folder_id': None})
@app.route('/home/<folder_id>')

def home_page(folder_id):
    if 'credentials' not in session:
        return redirect(url_for('index'))
    service = get_service()

    # decide which folder to show; None → root
    parent = folder_id if folder_id else 'root'

    # list *all* items in that folder
    resp = service.files().list(
        q=f"'{parent}' in parents and trashed=false",
        fields="*",
        pageSize=100
    ).execute()
    items = resp.get('files', [])

    # split into folders vs files
    folders = [f for f in items if f['mimeType']=='application/vnd.google-apps.folder']
    files   = [f for f in items if f['mimeType']!='application/vnd.google-apps.folder']

    return render_template('home.html',
                            files=files,
                            folders=folders,
                            current_folder=parent)





@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'credentials' not in session:
        return redirect(url_for('index'))

    service = get_service()
    if not hasattr(service, 'files'):
        return service

    if request.method == 'POST':
        uploaded_file = request.files['uploaded_file']
        # here we save the name ( not id not type )
        uploaded_file.save(uploaded_file.filename)
        file_metadata = {'name': uploaded_file.filename}
        media = MediaFileUpload(uploaded_file.filename, resumable=True)
        service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        media._fd.close()  
        os.remove(uploaded_file.filename)  
        return redirect(url_for('home_page'))

    return render_template('home.html')

@app.route('/delete/<file_id>')
def delete_file(file_id):
    if 'credentials' not in session:
        return redirect(url_for('index'))

    print("\n\n____________function delete_file called______________\n\n")
    service = get_service()
    service.files().update(
        fileId=file_id,
        body={'trashed': True}
    ).execute()
    return redirect(url_for('home_page'))

@app.route('/download/<file_id>')
def download_file(file_id):
    if 'credentials' not in session:
        return redirect(url_for('index'))
    service = get_service()
    meta = service.files().get(fileId=file_id, fields='name,mimeType').execute()
    mime = meta['mimeType']
    if mime.startswith('application/vnd.google-apps'):
        export_map = {
            'application/vnd.google-apps.document': 'application/pdf',
            'application/vnd.google-apps.spreadsheet': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.google-apps.presentation': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        }
        export_mime = export_map.get(mime, 'application/pdf')
        data = service.files().export(fileId=file_id, mimeType=export_mime).execute()
    else:
        data = service.files().get_media(fileId=file_id).execute()
    buf = BytesIO(data)
    return send_file(buf, as_attachment=True ,
      download_name=meta['name'],
      mimetype=export_mime 
      if mime.startswith('application/vnd.google-apps') else mime)





@app.route('/logout')
def logout():
    print("\n\n____________function logout called______________\n\n")
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run('localhost', 5000, debug=True)
