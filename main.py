from flask import Flask, request, redirect, render_template, url_for, flash
from werkzeug.utils import secure_filename
from firebase_admin import auth


# with open(r'config_files\app_config.json') as json_data_file:
#    data = json.load(json_data_file)

app = Flask(__name__)
# app.secret_key = data["SECRET_KEY"]
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/', methods=['GET', 'POST'])
# def index():
#     return render_template('index.html')
def hello():

    if request.method == "POST":

        # Check the file input type

        if 'input_image' not in request.files:
            #flash('No file part')
            print('No file part')
            return redirect(request.url)

        file = request.files['input_image']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file')
            print('No selected file')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

        return '''
        <!doctype html>
        <html>
        <body>
        This is a long text to test if data is passed correctly.
        <br>
        The store selected was {} and the file was called {}
        </body>
        </html>
        '''.format(request.form["store_name"], filename)

    return render_template("auth.html")


@app.route('/upload', methods=['GET'])
def upload():
    #return "<h1> this is a test </h1>"
    return render_template("upload.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] != 'admin' or \
                request.form['password'] != 'secret':
            error = 'Invalid credentials'
        else:
            flash('You were successfully logged in')
            return redirect(url_for('index'))
    return render_template('login.html', error=error)


if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    # Flask's development server will automatically serve static files in
    # the "static" directory. See:
    # http://flask.pocoo.org/docs/1.0/quickstart/#static-files. Once deployed,
    # App Engine itself will serve those files as configured in app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
# [START gae_python37_render_template]
