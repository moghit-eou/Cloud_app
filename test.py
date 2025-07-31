from flask import Flask, request, redirect, session, url_for, render_template_string
import os
import json
import google_auth_oauthlib.flow
import google.oauth2.credentials
import googleapiclient.discovery

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

app = Flask(__name__)
app.secret_key = os.urandom(24)

CLIENT_SECRETS_FILE = "credentials.json"
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

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

@app.route('/')
def index():
    print("\n\n ____________function index called______________ \n\n")
    if 'credentials' not in session:
        return '<a href="/authorize">Login with Google</a>'
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
   
    creds = google.oauth2.credentials.Credentials(**session['credentials'])
    service = googleapiclient.discovery.build('drive', 'v3', credentials=creds)
    results = service.files().list(pageSize=10, fields="files(id, name)").execute()
    files = results.get('files', [])
    html = '<h2>Your Google Drive Files</h2><ul>'
    for f in files:
        html += f"<li>{f['name']} ({f['id']})</li>"
    html += '</ul><a href="/logout">Logout</a>'
    return render_template_string(html)

@app.route('/logout')
def logout():
    print("\n\n____________function logout called______________\n\n")
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run('localhost', 5000, debug=True)
