import os
from datetime import datetime

# Imports the Google Cloud client library
from google.cloud import datastore
from google.cloud import storage

from gcp_interactions import gcp_clients
# This defaults to "prod". Override with "dev" for local runs
gcp_clients.ENVIRONMENT = "prod"

# This is only used locally:
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
DATASTORE_KIND_TRANSACTIONS = "transaction"

""" SESSION VARIABLES """

debug = False

# Initiate gcp clients
datastore_client = gcp_clients.init_service_client(service="datastore")
storage_client = gcp_clients.init_service_client(service="storage")


""" STORAGE BUCKET """


def upload_blob(file, user, store_name):
    """ Uploads a file to the bucket.
        params:
            file (blob): file to upload
            user (str): name of user that uploaded file
            store_name (str): name of the store of the receipt
    """
    # storage_client = storage.Client()
    bucket = storage_client.bucket(UNPROCESSED_BUCKET_NAME)
    now = datetime.today().strftime('%Y-%m-%d-%H:%M:%S')
    destination_blob_name = "image" + now

    blob = bucket.blob(destination_blob_name)

    # Add the uploading user to the metadata
    metadata = {"uploaded_by": user, "store_name": store_name}
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
    categories[0] = "Ikke tildelt"

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
    :param updates (dict): key: partial key to the item name, value: new category (int)
    """

    # {'avokado modnet 2pk': 804}
    for item in updates:
        key = datastore_client.key(DATASTORE_KIND_CATEGORY_ASSIGNMENT, item)
        task = datastore_client.get(key)

        new_id = updates[item]
        if new_id.isnumeric():
            new_id = int(new_id)
            task["cat_id"] = new_id
            datastore_client.put(task)
        else:
            print("Found an error in datastore.py > update_item_category. Non-numeric category id")


def get_all_entities_from_kind_as_df(entity_kind):
    """
    Gets all transactions for a given kind
    Returns: pandas.DataFrame
    """
    import pandas as pd
    query = datastore_client.query(kind=entity_kind)
    q_result = query.fetch()

    df = pd.DataFrame(q_result)

    # TODO, make sure keys are also included

    return df


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


def manual_upload_category():
    # NB BOTH cat_id and "value" as strings!
    articles_querified = [["cat_id", "value"], ["cat_id2", "value2"]]
    articles_querified = [
        ]

    task_list = []        # Used for bulk upload to datastore

    # Loop over all articles and insert one by one
    for article in articles_querified:
        id = article[0]
        # Only happens if we have not seen this item before. Then we add it to
        # unmapped items with an id of -1.

        task_key = datastore_client.key(DATASTORE_KIND_CATEGORIES, id)
        task = datastore.Entity(key=task_key)
        task["cat_id"] = article[1]

        task_list.append(task)
        print('Added {}: {}'.format(task.key.name, task['cat_name']))

        # End for loop

    # Saves multiple entities at once:
    datastore_client.put_multi(task_list)
