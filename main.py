from flask import Flask, request, redirect, render_template, url_for, flash, jsonify
from werkzeug.utils import secure_filename
# from firebase_admin import auth

import os
import pandas as pd
# from os.path import join, dirname
# from dotenv import load_dotenv

import google.oauth2.id_token
import google.auth.transport.requests
# import requests_toolbelt.adapters.appengine

# Import local functions
from gcp_interactions.datastore import (
    upload_blob,
    get_missing_category,
    get_all_categories,
    get_main_categories,
    update_item_category,
    get_all_entities_from_kind_as_df
    )

# Import analytics utilityFunctions
from scripts.analytics import (
    expenses_by_level
    )

# Define CONSTANTS
DATASTORE_KIND_CATEGORY_ASSIGNMENT = "category_item_mapping"
DATASTORE_KIND_CATEGORIES = "category"
DATASTORE_KIND_TRANSACTIONS = "transaction"

# dotenv_path = join(dirname(__file__), '.env')
# load_dotenv(dotenv_path)

# Use the App Engine Requests adapter. This makes sure that Requests uses
# URLFetch.
# requests_toolbelt.adapters.appengine.monkeypatch()
HTTP_REQUEST = google.auth.transport.requests.Request()

app = Flask(__name__)
# app.secret_key = data["SECRET_KEY"]
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

firebaseConfig = {
  "apiKey": "AIzaSyAfeYX2LU7mNDxfupyeMCb0HmJ1MCO4KqQ",  # os.environ['FIREBASE_API_KEY'],
  "authDomain": "expense-analyzer-260008.firebaseapp.com",
  "databaseURL": "https://expense-analyzer-260008.firebaseio.com",
  "projectId": "expense-analyzer-260008",
  "storageBucket": "expense-analyzer-260008.appspot.com",
  "messagingSenderId": "438670908109",
  "appId": "1:438670908109:web:4cb0e83043cbe89ac82784"
}


def allowed_file(filename):
    # Used for testing
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_user(req):
    # Used for testing
    return 1


@app.route("/index", methods=["GET"])
# Used for testing
def test():
    return render_template("index.html")


@app.route('/loggedIn', methods=["GET"])
# Used for testing
def authorize():
    user = {'username': 'Mikkel'}
    return render_template("check_user.html", title="test_user", user=user)


@app.route('/', methods=['GET', 'POST'])
# def index():
#     return render_template('index.html')
def hello():
    if request.method == "POST":
        # Check the file input type
        if 'input_image' not in request.files:
            print('No file part')
            return redirect(request.url)
        file = request.files['input_image']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
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


def has_token(headers):
    # Used for testing
    """ Determined if header contains authorization token

    params:
        headers (dict): with a field Authorization

    returns boolean
    """
    return True


@app.route('/upload', methods=['GET'])
def upload():
    print("on upload route")
    return render_template("upload.html")


@app.route("/uploadImageToBucket", methods=["GET", "POST"])
def uploadImageToBucket():
    # Called from upload.htlm. Main upload entrypoint
    print("READY TO UPLOAD FILE")

    # Check the file input type
    if request.method == "POST":
        if 'input_image' not in request.files:
            print('No file part')
            # return redirect(request.url)
            return '''<!doctype html>
                <html>
                <body>
                NO FILE WAS FOUND!
                <br>
                </body>
                </html>'''
        file = request.files['input_image']
        user = request.form["user"]
        # if user does not select file, browser also submit an empty part without filename
        if file.filename == '':
            print('No selected file')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

        # Save file to DataStore!
        upload_blob(file, user)

        return '''
        <!doctype html>
        <html>
        <body>
        {% include 'navigationBar.html' %}
        This is a long text to test if data is passed correctly.
        <br>
        The store selected was {} and the file was called {}
        </body>
        </html>
        '''.format(request.form["store_name"], filename)
    else:
        return '''<!doctype html>
            <html>
            <body>
            GOT A GET REQUEST, NOT POST
            <br>
            </body>
            </html>'''


@app.route("/assignCategories", methods=["GET", "POST"])
def assignCategories():
    """ This function structures and returns and table where the user can
        go through all unassigned items and assign a category """

    if request.method == "GET":
        # First run the missing categories function
        items_without_category = get_missing_category(10)
        item_names_without_category = []

        for cat in items_without_category:
            item_names_without_category.append(cat.key.id_or_name)

        # Run a function that fetches all possible categories
        all_categories = get_all_categories()
        all_main_categories = get_main_categories(all_categories)

        # Return the list of items in a tabular format

        # Await feedback from user. Make a way to search in the categories

        # Iterate through the user feedback and write back to the datastore

        # Give the user two choices: 10 more, go back
        return render_template("missing_categories.html",
                               item_list=item_names_without_category,
                               category_dict=all_categories,
                               main_category_dict=all_main_categories)

    elif request.method == "POST":
        # PARSE TABLE INPUT!
        form_data = request.form

        # Values are on the format item1: category1

        updated_categories = {}  # Key is item name, value is new category

        for key in form_data.keys():
            if "item" in key:
                input_number = key.replace("item", "")
                category_key = "category"+input_number

                item_key = form_data[key]
                category = form_data[category_key]

                updated_categories[item_key] = category

        # Call function to udpate values in google datastore
        update_item_category(updated_categories)

        return render_template("missing_categories.html")


@app.route('/utilityFunctions', methods=['GET'])
def utilityFunctions():
    """ Collection of utility functions, e.g. to trigger GCP functions """
    return render_template("utilityFunctions.html")


@app.route('/analytics', methods=['GET'])
def analytics():
    """ Main page for analysis of expenditures """

    transactions = get_all_entities_from_kind_as_df(DATASTORE_KIND_TRANSACTIONS)
    expense_by_main_cat = expenses_by_level(transactions, 2)
    expense_by_main_cat = expense_by_main_cat.reset_index()

    return render_template("analytics.html",
                           expense_by_main_cat=expense_by_main_cat)


@app.route('/history', methods=['GET'])
def history():
    """ Main page for overview of receipts """
    return render_template("history.html")


@app.route("/getExpenses", methods=["GET"])
def getExpenses():
    # Used for testing
    """ Returns expenses from the DB."""
    print("ON getExpense ROUTE!")
    print("Headers: ", request.headers)

    # Check if there exists an "Authorization" field, if not, log in first
    if "Authorization" not in request.headers:
        print("Missing auth token!")
        # return render_template("index.html", redirect_from="upload")
        return 'Unauthorized, missing token', 401
    else:
        # Verify the Firebase auth
        print("Contains auth token")
        # [START verify_token]
        id_token = request.headers['Authorization'].split(' ').pop()
        claims = google.oauth2.id_token.verify_firebase_token(
            id_token, HTTP_REQUEST)
        if not claims:
            return 'Unauthorized', 401
        # [END verify_token]
        # expenses = query_database(claims['sub'])
        expenses = {"message": "Expenses are coming here!"}

        return jsonify(expenses)
        # return render_template("upload.html", token=id_token)


@app.route('/login', methods=['GET', 'POST'])
def login():
    # Used for testing
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
