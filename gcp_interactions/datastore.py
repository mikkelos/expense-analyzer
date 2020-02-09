# import os
from datetime import datetime

# Imports the Google Cloud client library
from google.cloud import datastore
from google.cloud import storage
# from google.oauth2 import service_account

""" CONSTANTS """
# STORAGE BUCKET NAMES
UNPROCESSED_BUCKET_NAME = "unprocessed_expense_bucket_1"
PROCESSED_BUCKET_NAME = "processed_expense_bucket_1"

# this controls the threshold for the degree of overlap between an scewed text
# box and the rest of the line for it to be allocated
OVERLAPPING_ALLOCATION_THRESHOLD = 0.3

# The entity kind in datastore to query to find previous assignments
DATASTORE_KIND_CATEGORY_ASSIGNMENT = "category_item_mapping"
DATASTORE_KIND_CATEGORIES = "category"

""" SESSION VARIABLES """

debug = False
developing = True
local_run = False

"""
# This is only used for local development:
key_path = "/Volumes/GoogleDrive/My Drive/00. My Documents/03. Internt/24. Expense analyzer/config_files/expense-analyzer-260008-0cac2ecd3671.json"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
credentials = service_account.Credentials.from_service_account_file(
    key_path,
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
# Instantiate clients
datastore_client = datastore.Client(
    credentials=credentials
)
"""

datastore_client = datastore.Client()


""" STORAGE BUCKET """


def upload_blob(file, user):
    """ Uploads a file to the bucket."""
    """
    if local_run:
        storage_client = storage.Client(
            credentials=credentials
        )
    else:
        storage_client = storage.Client()
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(UNPROCESSED_BUCKET_NAME)
    now = datetime.today().strftime('%Y-%m-%d-%H:%M:%S')
    destination_blob_name = "image" + now

    blob = bucket.blob(destination_blob_name)

    # Add the uploading user to the metadata
    metadata = {"uploaded_by": user}
    blob.metadata = metadata

    # Upload file
    blob.upload_from_file(file)

    print('Blob {} uploaded to bucket {}.'.format(
        file.filename,
        bucket.name
        ))


""" DATASTORE """


def get_missing_category(max_records):
    """
    :param max_records (int): number of items to return
    :return: a number of unclassified items from the category assignment
             registry
    """

    query = datastore_client.query(kind=DATASTORE_KIND_CATEGORY_ASSIGNMENT)
    query.add_filter("cat_id", "=", -1)

    # Fetch first X results
    q_result = query.fetch(limit=max_records)
    return list(q_result)


def get_all_categories():
    """ Get all the categories in the db
    :return: key:value pairs from the DB containing the categories
    """
    query = datastore_client.query(kind=DATASTORE_KIND_CATEGORIES)
    q_result = query.fetch()

    categories = {}
    # Add the dummy value for unassigned
    categories[-1] = "Ikke tildelt"

    for entity in list(q_result):
        key = entity.key.id_or_name
        category = entity["cat_name"]
        categories[key] = category

    return categories


def get_main_categories(categories):
    """ Given a list of categories, returns the top level categories with name"""
    main_categories = {}
    for key in categories.keys():
        if len(str(key)) <= 2:
            main_categories[key] = categories[key]
    return main_categories


def update_item_category(updates):
    """ Does a bulk update of item-category mappings
    :param updates (dict): key: partial key to the item name, value: new category
    """

    # {'avokado modnet 2pk': 804}
    for item in updates:
        key = datastore_client.key('category_item_mapping', item)
        task = datastore_client.get(key)
        task["cat_id"] = updates[item]
        datastore_client.put(task)


def upload_categories():
    """
    Uploades categories based on excel file
    TODO: TEST A BIT BEFORE RERUNNING!
    """
    import pandas as pd
    filepath = "../data/varekategorier.xlsx"
    cats = pd.read_excel(filepath)

    # The kind for the new entity
    kind = 'category'

    for cat in cats.iterrows():
        # The Cloud Datastore key for the new entity
        category_id = str(cat[1]["Varegruppe"])
        task_key = datastore_client.key(kind, category_id)

        # Prepares the new entity
        task = datastore.Entity(key=task_key)
        task['cat_name'] = cat[1]["VAREGRUPPE NAVN"]

        if debug:
            print("Writting to datastore:", task)

        # Saves the entity
        datastore_client.put(task)
