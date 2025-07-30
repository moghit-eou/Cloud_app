from flask import Flask, jsonify

app = Flask(__name__ , static_folder = 'static' , template_folder = 'templates') 



@app.route("/")
def home():
    return jsonify({"message": "Welcome to the Flask app!"})








if __name__ == '__main__':
    app.run(debug=True)