import os
# Imports the Google Cloud client library
from google.cloud import datastore
from google.cloud import storage
from google.oauth2 import service_account

# Controls whether the client is created with credentials from a config file
ENVIRONMENT = "prod"

KEY_PATH = "/Volumes/GoogleDrive/My Drive/00. My Documents/03. Internt/24. Expense analyzer/config_files/expense-analyzer-260008-0cac2ecd3671.json"


def init_service_client(service):
    client = ""
    if ENVIRONMENT == "prod":
        # Credentials are read internally when deployed to GCP
        if service == "datastore":
            client = datastore.Client()
        elif service == "storage":
            client = storage.Client()

    elif ENVIRONMENT == "dev":
        # assign a credential file
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = KEY_PATH
        credentials = service_account.Credentials.from_service_account_file(
            KEY_PATH,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        # Instantiate client
        if service == "datastore":
            client = datastore.Client(
                credentials=credentials
            )
        elif service == "storage":
            client = storage.Client(
                credentials=credentials
            )

    return client
