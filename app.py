from flask import Flask, request, redirect, session, url_for, render_template_string , render_template , session , jsonify , flash
import os
import json
import google_auth_oauthlib.flow
import google.oauth2.credentials
import googleapiclient.discovery
from googleapiclient.http import MediaFileUpload
from io import BytesIO
from flask import send_file
from helper import annotate_files, filter_and_sort , get_folder_path, credentials_to_dict
from dotenv import load_dotenv
from datetime import timedelta 


load_dotenv()

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')

if not app.secret_key:
    raise ValueError("LOL FLASK_SECRET_KEY env var not set FIX IT lol")

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
)

SCOPES = ['https://www.googleapis.com/auth/drive']

def get_flow():
    creds_json = os.getenv("GOOGLE_CREDENTIALS")

    if not creds_json: #debugging purposes
        raise ValueError("GOOGLE_CREDENTIALS environment variable not set FIX IT lol")
    
    creds_data = json.loads(creds_json)
    
    redirect_uri = url_for('oauth_callback', _external=True)
    
    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        creds_data,
        scopes=SCOPES,
        redirect_uri=redirect_uri  
    )
    
    return flow



def get_service():
    creds = google.oauth2.credentials.Credentials(**session['credentials'])
    return googleapiclient.discovery.build('drive', 'v3', credentials=creds)





@app.route('/')
def index():
    if 'credentials' not in session:
        return render_template('login.html')

    return redirect(url_for('home_page'))

@app.route('/authorize')
def authorize():
    flow = get_flow()
    auth_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    session['state'] = state
    return redirect(auth_url)



@app.route('/oauth_callback')
def oauth_callback():
    flow = get_flow()
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session['credentials'] = credentials_to_dict(credentials)
    session.permanent = True
    return redirect(url_for('home_page'))




@app.route('/home', defaults={'folder_id': None})
@app.route('/home/<folder_id>')
def home_page(folder_id):
    if 'credentials' not in session:
        return redirect(url_for('index'))

    service = get_service()


    parent = folder_id if folder_id else 'root'


    resp = service.files().list(
        q=f"'{parent}' in parents and trashed=false",
        fields="*",
        pageSize=100
    ).execute()
    items = resp.get('files', [])

    folders = [f for f in items if f['mimeType']=='application/vnd.google-apps.folder']
    files   = [f for f in items if f['mimeType']!='application/vnd.google-apps.folder']

    files = annotate_files(files)
    files = filter_and_sort(files,
                            wanted_type=request.args.get('type', 'all'),
                            sort_by=request.args.get('sort', 'name'))   

    return render_template('home.html',
                            files=files,
                            folders=folders,
                            current_folder=parent,
                            wanted_type=request.args.get('type', 'all'),
                            sort_by=request.args.get('sort', 'name')
                            )


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))
    
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

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'credentials' not in session:
        return redirect(url_for('index'))

    service = get_service()
    if not hasattr(service, 'files'):
        return service


    uploaded_file = request.files['uploaded_file']

    
    if not uploaded_file:
        return redirect(url_for('home_page'))

    uploaded_file.save(uploaded_file.filename)
    
    file_metadata = {'name': uploaded_file.filename}
    folder_id = request.args.get('folder_id')
    
    if folder_id:
        file_metadata['parents'] = [folder_id]

    media = MediaFileUpload(uploaded_file.filename, resumable=True)
    service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()
    media._fd.close()  
    os.remove(uploaded_file.filename)  
    return redirect(url_for('home_page' , folder_id =folder_id))

@app.route('/delete/<file_id>')
def delete_file(file_id):

    if 'credentials' not in session:
        return redirect(url_for('index'))

    service = get_service()
    service.files().update(
        fileId=file_id,
        body={'trashed': True}
    ).execute()

    folder_id = request.args.get('folder_id')
    if folder_id:
        return redirect(url_for('home_page',folder_id=folder_id))

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


@app.route('/add_folder', methods=['POST'])
def add_folder():
    if 'credentials' not in session:
        return redirect(url_for('home'))

    service   = get_service()
    parent_id = request.args.get('parent_id') or 'root'
    folder_name = request.form.get('folder_name', '').strip()
    if not folder_name:
        return redirect(url_for('home_page', folder_id=parent_id))

    metadata = {
        'name':     folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents':  [parent_id]
    }

    service.files().create(body=metadata, fields='id').execute()
    return redirect(url_for('home_page', folder_id=parent_id))


@app.route('/delete_folder/<folder_id>')
def delete_folder(folder_id):

    if 'credentials' not in session:
        return redirect(url_for('index'))

    service = get_service()
    # move the folder to trash
    service.files().update(
        fileId=folder_id,
        body={'trashed': True}
    ).execute()

    # read parent_id to know where to redirect
    parent = request.args.get('parent_id')
    return redirect(url_for('home_page', folder_id=parent))


@app.route('/rename_folder/<folder_id>', methods=['POST'])
def rename_folder(folder_id):
    if 'credentials' not in session:
        return redirect(url_for('index'))

    new_name = request.form.get('new_name', '').strip()
    if not new_name:
        flash('Folder name cannot be empty', 'warning')
        return redirect(request.referrer or url_for('home_page'))
    service = get_service()
    service.files().update(fileId=folder_id, body={'name': new_name}).execute()
    flash(f'Folder renamed to "{new_name}"', 'success')
    parent = request.form.get('parent_id')
    if parent: 
        return redirect(url_for('home_page', folder_id=parent))
    return redirect(url_for('home_page'))




if __name__ == '__main__':
    app.run(host = "0.0.0.0", port = 5000, debug=True)
