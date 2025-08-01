from flask import Flask, request, redirect, session, url_for, render_template_string , render_template , session
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


@app.route('/home')
def home_page():
    print("\n\n____________function list_files called______________\n\n")
    
    if 'credentials' not in session:
        return redirect(url_for('index'))
        ## Ensure creds are valide
    service = get_service()
    results = service.files().list(pageSize=5, 
    fields="*" ,
    q = "trashed=false"
    ).execute()
    
    
    files = results.get('files', [])
    return render_template('home.html' , files=files)



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
