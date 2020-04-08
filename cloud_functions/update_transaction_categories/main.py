"""
gcloud functions deploy update_transaction_categories --region europe-west1 --runtime python37 --trigger-http  --entry-point update_transaction_categories
"""
import os

# Imports the Google Cloud client library
from google.cloud import datastore
from google.oauth2 import service_account

DATASTORE_KIND_TRANSACTIONS = "transaction"
DATASTORE_KIND_MAPPING = "category_item_mapping"


def update_transaction_categories():
    """ Runs the functions in order """

    """ Use this when deployed on google cloud """
    datastore_client = datastore.Client()

    trans_without_cat = get_transactions_without_category(datastore_client)
    existing_mappings = get_all_existing_mappings(datastore_client)
    trans_with_new_cat = filter_against_known_mappings(trans_without_cat, existing_mappings)

    bulk_update(datastore_client, trans_with_new_cat)

    return "Updated " + str(len(trans_with_new_cat)) + " entities"


def get_transactions_without_category(datastore_client):
    """ Get all the transactions in the db without category
    :return: key:value pairs from the DB containing the transactions
    """
    query = datastore_client.query(kind=DATASTORE_KIND_TRANSACTIONS)

    # query = query.add_filter('cat_id', '<=', 0). Bug? returns None
    q_result = query.fetch()
    transaction_keys_no_cat = {}

    for entity in list(q_result):
        key = entity.key.id_or_name
        category_id = entity["cat_id"]
        item_name = entity["item_name"]

        if category_id <= 0:
            # I.e. cat is 0 or -1
            transaction_keys_no_cat[key] = item_name

    return transaction_keys_no_cat


def get_all_existing_mappings(datastore_client):
    """ Get all existing mappings in a dictionary on form name:cat_id """

    query = datastore_client.query(kind=DATASTORE_KIND_MAPPING)
    q_result = query.fetch()

    # Create a simple map from name to known cat_id
    mappings = {}
    count_mapped = 0
    count_unmapped = 0

    for entity in q_result:
        key = entity.key.id_or_name
        category = entity["cat_id"]
        if category == -1:
            count_unmapped += 1
        else:
            count_mapped += 1
            mappings[key] = category

    # print("Mapped", count_mapped)
    # print("Unmapped", count_unmapped)
    return mappings


def filter_against_known_mappings(transaction_keys_no_cat, mappings):
    """ Takes in two dictionaries. For every item name for a key in the first,
        if it is in mappings, update it.
        Returns: dict from key to new cat_id """

    keys_to_update = {}

    for key in transaction_keys_no_cat.keys():
        item_name = transaction_keys_no_cat[key]
        if item_name in mappings.keys():
            keys_to_update[key] = mappings[item_name]

    return keys_to_update


def bulk_update(datastore_client, updates):
    """ Does a bulk update of transactions category ids
    :param updates (dict): key: partial key to the transaction id, value: new category (int)
    """

    # {'avokado modnet 2pk': 804}
    for item in updates:
        key = datastore_client.key(DATASTORE_KIND_TRANSACTIONS, item)
        task = datastore_client.get(key)

        new_id = updates[item]
        task["cat_id"] = new_id
        datastore_client.put(task)


if __name__ == '__main__':
    print("Running locally")

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

    trans_without_cat = get_transactions_without_category(datastore_client)
    existing_mappings = get_all_existing_mappings(datastore_client)
    trans_with_new_cat = filter_against_known_mappings(trans_without_cat, existing_mappings)

    bulk_update(trans_with_new_cat)
