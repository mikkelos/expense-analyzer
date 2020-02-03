
# Imports the Google Cloud client library
import os
from google.cloud import datastore
from google.oauth2 import service_account

""" CONSTANTS """
# STORAGE BUCKET NAMES
UNPROCESSED_BUCKET_NAME = "unprocessed_expense_bucket_1"
PROCESSED_BUCKET_NAME = "processed_expense_bucket_1"

# this controls the threshold for the degree of overlap between an scewed text
# box and the rest of the line for it to be allocated
OVERLAPPING_ALLOCATION_THRESHOLD = 0.3

# The entity kind in datastore to query to find previous assignments
DATASTORE_KIND_CATEGORY_ASSIGNMENT = "category_item_mapping"

""" SESSION VARIABLES """
user_name = "testuser"

debug = False
developing = True
local_run = False

key_path = "/Volumes/GoogleDrive/My Drive/00. My Documents/03. Internt/24. Expense analyzer/config_files/expense-analyzer-260008-0cac2ecd3671.json"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
credentials = service_account.Credentials.from_service_account_file(
    key_path,
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
# Instantiates a client
datastore_client = datastore.Client(
    credentials=credentials
)


def missing_category(max_records):
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
