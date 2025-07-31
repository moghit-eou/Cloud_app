from flask import Flask, request, redirect, session, url_for, render_template_string , render_template , session
import os
import json
import google_auth_oauthlib.flow
import google.oauth2.credentials
import googleapiclient.discovery
from googleapiclient.http import MediaFileUpload


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

    return redirect(url_for('list_files'))

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
    return redirect(url_for('list_files'))


@app.route('/files')
def list_files():
    print("\n\n____________function list_files called______________\n\n")
    
    if 'credentials' not in session:
        return redirect(url_for('index'))
        ## Ensure creds are valide
    service = get_service()
    results = service.files().list(pageSize=2, fields="*").execute()
    files = results.get('files', [])
    return render_template('list_files.html' , files=files)



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
        return redirect(url_for('list_files'))

    return render_template('upload.html')



@app.route('/logout')
def logout():
    print("\n\n____________function logout called______________\n\n")
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run('localhost', 5000, debug=True)
