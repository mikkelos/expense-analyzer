
"""
GCP deploy command: gcloud functions deploy gcs_trigger_generic --runtime python37 --trigger-resource unprocessed_expenses --trigger-event google.storage.object.finalize
# --entry-point to define a different entry function than gcs_trigger_generic

gcloud functions deploy process_expense --region europe-west1 --runtime python37 --trigger-resource unprocessed_expense_bucket_1 --trigger-event google.storage.object.finalize --entry-point gcs_trigger
"""

# Imports the Google Cloud client library
from google.cloud import storage
from google.cloud import vision
from google.cloud import datastore
# from google.oauth2 import service_account
import io
import os  # for use with setting env variables
import re
from datetime import datetime

# TODO
# Change from TESTUSER To user from metadata of image_uri
# Change image name of blob, so that it instead contains a datestamp


# STORAGE BUCKET NAMES
UNPROCESSED_BUCKET_NAME = "unprocessed_expense_bucket_1"
PROCESSED_BUCKET_NAME = "processed_expense_bucket_1"

# this controls the threshold for the degree of overlap between an scewed text
# box and the rest of the line for it to be allocated
OVERLAPPING_ALLOCATION_THRESHOLD = 0.3

# The entity kind in datastore to query to find previous assignments
DATASTORE_KIND_CATEGORY_ASSIGNMENT = "category_item_mapping"

user_name = "testuser"

debug = False
developing = True
local_run = False

"""
# Only used in dev environment
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
vision_client = vision.ImageAnnotatorClient(
    credentials=credentials
)
# vision_client = vision.ImageAnnotatorClient.from_service_account_json(key_path)

"""
datastore_client = datastore.Client()
vision_client = vision.ImageAnnotatorClient()


def gcs_trigger(data, context):
    """Background Cloud Function to be triggered by Cloud Storage.
       This generic function logs relevant data when a file is changed.

    Args:
        data (dict): The Cloud Functions event payload.
        context (google.cloud.functions.Context): Metadata of triggering event.
    Returns:
        None; the output is written to Stackdriver Logging
    """

    file_name = data['name']

    print('Event ID: {}'.format(context.event_id))
    print('Event type: {}'.format(context.event_type))
    print('Bucket: {}'.format(data['bucket']))
    print('File: {}'.format(data['name']))
    print('Metageneration: {}'.format(data['metageneration']))
    print('Created: {}'.format(data['timeCreated']))
    print('Updated: {}'.format(data['updated']))

    """ Move file to the processed bucket """
    change_storage_bucket(UNPROCESSED_BUCKET_NAME, file_name, PROCESSED_BUCKET_NAME, file_name)

    """ Call the vision API to extract information """
    path = "gs://"+PROCESSED_BUCKET_NAME+"/"+file_name
    response = detect_text(path)

    """ Extract the expense lines """
    relevant_lines, receipt_id_and_datetime = article_lines_coop(response)
    receipt_lines = allocate_lines_coop(relevant_lines)
    actual_lines = lines_to_text(receipt_lines)
    articles_querified = query_preparation(actual_lines)

    """ Extract the receipt id and datetime before saving to datastore """
    receipt_id = receipt_id_and_datetime.split(" ")[0].strip()
    receipt_date = receipt_id_and_datetime.split(" ")[1].strip()
    datetime_object = datetime.strptime(receipt_date, '%m.%d.%Y')

    """ Get username from blob metadata """
    # Instantiates a client
    storage_client = storage.Client()
    bucket = storage_client.bucket(PROCESSED_BUCKET_NAME)
    blob = bucket.get_blob(file_name)
    metadata = blob.metadata

    if(metadata):
        user_name = blob.metadata["uploaded_by"]

    """ Write result to DB """
    writeToDatastore(articles_querified, user_name, datetime_object, receipt_id)


def change_storage_bucket(bucket_name, blob_name, new_bucket_name, new_blob_name):
    """"Copies a blob from one bucket to another with a new name"""

    print("Moving file from unprocessed to processed")

    # Instantiates a client
    storage_client = storage.Client()

    source_bucket = storage_client.get_bucket(bucket_name)
    source_blob = source_bucket.blob(blob_name)

    destination_bucket = storage_client.get_bucket(new_bucket_name)
    new_blob = source_bucket.copy_blob(source_blob, destination_bucket)

    print('Blob {} in bucket {} copied to blob {} in bucket {}.'.format(
        source_blob.name,
        source_bucket.name,
        new_blob.name,
        destination_bucket.name
        ))

    # If blob is actually copied, then delete it in the old storage
    # blobs = list(destination_bucket.list_blobs())
    if destination_bucket.get_blob(blob_name) is not None:
        # Then the blob exists in destination, and safe to remove from source
        source_bucket.delete_blob(blob_name)
    else:
        print("Failed to copy blob {} to new bucket and delete old".format(blob_name))


def crop_and_rotate(path):
    return 1


def detect_text(path):
    """Detects text in the file."""

    # vision_client = vision.ImageAnnotatorClient()
    """
    blob = storage_client.bucket(bucket_name).get_blob(file_name)
    blob_uri = f'gs://{bucket_name}/{file_name}'
    blob_source = {'source': {'image_uri': blob_uri}}
    # Ignore already-blurred files
    if file_name.startswith('blurred-'):
        print(f'The image {file_name} is already blurred.')
        return

    print(f'Analyzing {file_name}.')
    result = vision_client.safe_search_detection(blob_source)
    """

    """ ONLY USED FOR LOCAL FILES """
    if local_run:
        with io.open(path, 'rb') as image_file:
            content = image_file.read()

        image = vision.types.Image(content=content)
    else:
        image = {'source': {'image_uri': path}}

    response = vision_client.text_detection(image=image)
    texts = response.text_annotations

    if debug:
        print('Texts:')
        for text in texts:
            print('\n"{}"'.format(text.description))

            vertices = (['({},{})'.format(vertex.x, vertex.y)
                        for vertex in text.bounding_poly.vertices])

            print('bounds: {}'.format(','.join(vertices)))

    return response


#  ### PARSER FOR COOP
def article_lines_coop(response):
    # Locate the relevant range to extract items
    start_y_coordinate = -1     # Determine which point to start extract items
    end_y_coordinate = -1       # Determine which point to stop extract items

    receipt_id_and_datetime = ""

    for text in response.text_annotations:
        if len(text.description) > 100:
            # Full text, extract the receipt ID and datetime
            full_text = text.description

            # Start substring from the search term
            search_term = "Salgskvittering"
            start_index = full_text.find(search_term) + len(search_term)

            # End the substring at next newline
            end_index = start_index + full_text[start_index:].find("\n")

            # This now contains id, date, time, separated by space
            receipt_id_and_datetime = full_text[start_index:end_index].strip()
        elif "Salgskv" in text.description:
            start_y_coordinate = max(vertex.y for vertex in text.bounding_poly.vertices)
            if debug:
                print("Found starting point at {}, after text {}".format(start_y_coordinate, text.description))
        elif "Totalt" in text.description:
            end_y_coordinate = min(vertex.y for vertex in text.bounding_poly.vertices)
            if debug:
                print("Found ending point at {}, after text {}".format(end_y_coordinate, text.description))

    # Iterate through all lines, extract only those with item y coordinate larger than start and smaller than end
    relevant_items = []
    for text in response.text_annotations:
        if text.bounding_poly.vertices[0].y > start_y_coordinate and text.bounding_poly.vertices[0].y < end_y_coordinate:
            # print("Found an item line!: {}".format(text.description))
            relevant_items.append(text)

    return relevant_items, receipt_id_and_datetime


# Key = line_number, value = item
# Idea: For each bounding box, calculate the mid y coordinate. If this coordinate is inside the bounding box of
# another, then these are on the same line.
def allocate_lines_coop(items):
    """
    :param items: input is a list of relevant text boxes from Google vision, containing the text found and bounding polygon
    :return: returns a dictionary, with all items allocated to a line_id containing all elements on that same line, sorted by their x-coordinates
    """

    receipt_lines = {}
    # Key is the line number
    # Each value has the format [item]

    # Loop over all found text boxes
    for item in items:
        y_first_coor = item.bounding_poly.vertices[0].y
        y_fourth_coor = item.bounding_poly.vertices[3].y
        y_mean_coor = (y_first_coor + y_fourth_coor)/2
        height = y_fourth_coor - y_first_coor

        overlap_up = -1
        overlap_down = -1

        if len(receipt_lines) == 0:
            receipt_lines[0] = []
            receipt_lines[0].append(item)

        else:
            inserted = False

            # Loop through all allocated/identified lines
            for line in receipt_lines:
                # See if item belongs to an existing line
                # Compare against y coordinates of first item on line
                first_line_item = receipt_lines[line][0]
                first_line_item_y1 = first_line_item.bounding_poly.vertices[0].y
                first_line_item_y4 = first_line_item.bounding_poly.vertices[3].y

                # if mean coordinate is within min and max of line, add it to the line
                if first_line_item_y1 <= y_mean_coor <= first_line_item_y4:
                    receipt_lines[line].append(item)
                    inserted = True
                    break

                # These are used to calculate overlap between lines
                last_line_item = receipt_lines[line][-1]
                last_line_item_y1 = last_line_item.bounding_poly.vertices[0].y
                last_line_item_y4 = last_line_item.bounding_poly.vertices[3].y

                # Calculate a match% against each other line, to see if picture is slightly squished
                # Calculate against the item to the far right in the current line
                if last_line_item_y1 <= y_first_coor <= last_line_item_y4:
                    # Some overlap detected. item is below the line in comparison
                    overlap_down = float(last_line_item_y4 - y_first_coor) / height
                    if debug:
                        print("Found {}% overlap under between text {} and {} on line {}".format(overlap_down, item.description, first_line_item.description, line))

                if last_line_item_y1 <= y_fourth_coor <= last_line_item_y4:
                    # Some overlap detected. item is above the line in comparison
                    overlap_up = float(y_fourth_coor - last_line_item_y1) / height
                    if debug:
                        print("Found {}% overlap over between text {} and {} (first item) on line {}".format(overlap_up, item.description, first_line_item.description, line))

                # If any of the matches are above X%, allocate it to that line
                if overlap_down > OVERLAPPING_ALLOCATION_THRESHOLD or overlap_up > OVERLAPPING_ALLOCATION_THRESHOLD:
                    receipt_lines[line].append(item)
                    inserted = True
                    break

            # No match found against previous lines. Create a new line
            if not inserted:
                new_line_num = len(receipt_lines)
                receipt_lines[new_line_num] = []
                receipt_lines[new_line_num].append(item)

    # Sort each line by the x coordinates
    for line in receipt_lines:
        receipt_lines[line].sort(key=lambda item: item.bounding_poly.vertices[0].x)

    return receipt_lines


def lines_to_text(receipt_lines):
    """
    :param receipt_lines: takes a dictionary as input, where the key is a
            line_id and the value are objects containing the
            element text and bounding polygon
    :return: A list of text strings concatenated for each line, instead of
             google vision objects
    """
    receipt_text = []
    for line in receipt_lines:
        text = ""
        for item in receipt_lines[line]:
            text += " " + item.description
        receipt_text.append(text.lower().strip())
    return receipt_text


def query_preparation(receipt_text):
    """
    :param receipt_text: list of text strings containing article text and price
    :return: a list of dict line items, with keys:
            item_name: The full item name
            item_count: The number of items
            type:
            price_gross: The total price before discount
            price_net: The total price after discount
            unit_price_net: The unit price after dicount
            discount_amt: The total discount
            discount_type: Percentage, fixed, mix and match, etc
    """

    """
    Regex:
        "\d+" matches one or more digits
        "." followed by any charcter
        "\d+" one or more digits
        "$" at the end of the line
    """
    price_pattern = "(\d+.\d+)$"
    articles_querified = []

    curr_item_line = {}

    for article in receipt_text:
        if debug:
            print("------------")
            print(article)

        if "rabatt" in article:
            # TODO: x = re.spltt(discount_pattern, article)
            # articles.append(["discount", x[0], x[1]])

            discount_line = article.split(" ")
            # Will have the structure: ['rabatt:', 'nok', '13.16', '(40%', 'av', '32.90)']

            if len(discount_line) >= 3:
                discount_amt = discount_line[2]

                # A line starting with "Rabatt" belongs to the last item identified
                curr_item_line["discount_amt"] = discount_amt
                curr_item_line["discount_type"] = "percentage"
            else:
                print("Found an unknown discount format".format(article))

            if debug:
                print("Found a discount line")
                print(article.split(" "))

        elif "antall" in article:
            # Do something TODO

            antall_line = article.split(" ")
            # Will have the structure: ['antall:', '2', 'stk', '1.60', 'kr/stk']

            if len(discount_line) >= 4:
                item_count = antall_line[1]
                unit_price_net = antall_line[3]

                # A line starting with "antall" belongs to the last item identified
                curr_item_line["item_count"] = item_count
                curr_item_line["unit_price_net"] = unit_price_net

            if debug:
                print("Found a antall line")
                print(article.split(" "))

        elif "artikler" not in article:
            curr_item_line = {}
            x = re.split(price_pattern, article, 2)

            # Element 3, index 2, is always empty string
            if len(x) == 3:
                # actual article
                item = x[0].strip()
                price = x[1].strip()

                curr_item_line["item_name"] = item
                curr_item_line["price_net"] = price
                curr_item_line["price_gross"] = price
                curr_item_line["unit_price_net"] = price
                curr_item_line["item_count"] = 1

                articles_querified.append(curr_item_line)
                if debug:
                    print("len was 3")
                    print("Appending item '{}' with price '{}'. Full split is '{}'".format(item, price, x))
            else:
                # Typically weight times price per kg.
                if developing:
                    print("Unparsable line: {}".format(article))
        else:
            if developing:
                print("Unparsable line 2: {}".format(article))

    # Finally, iterate through the set of lines and update fields that are calculated by discounts
    for article in articles_querified:
        if "discount_amt" in article and "price_net" in article:

            discount = article.get("discount_amt").strip()
            price_net = article.get("price_net").strip()

            # Try convert to floats
            try:
                discount = float(discount)
                price_net = float(price_net)
                float_success = True
            except ValueError:
                float_success = False
                print("Unable to parse either {} or {}".format(discount, price_net))

            # Add discount to calculate gross price. Check parsability
            if float_success:
                article["price_gross"] = str(round((discount + price_net)*100)/100)

    return articles_querified


def fetch_item_category(item_name):
    """ Search through similar items and reuse their category
        Give it a category of 0 if it not seen before
    """

    query = datastore_client.query(kind=DATASTORE_KIND_CATEGORY_ASSIGNMENT)
    # query.add_filter("item_name", "=", item_name)

    # Create a filter on the key
    first_key = datastore_client.key(DATASTORE_KIND_CATEGORY_ASSIGNMENT, item_name)
    query.key_filter(first_key, '=')

    # Fetch only one result
    q_result = query.fetch(limit=1)

    category_id = 0
    for res in q_result:
        category_id = res["cat_id"]

    return category_id


def writeToDatastore(articles_querified, added_by, trans_datetime, receipt_id):
    """ Writes the arcitles to the datastore. On the way, look up the category
        mapping if this item has been categorized before. If not found, it will
        be created with an id of -1, so that it can be updated later
    :param articles_querified: list of dict possibly containing the following keys:
        item_name: The full item name
        item_count: The number of items
        price_gross: The total price before discount
        price_net: The total price after discount
        unit_price_net: The unit price after dicount
        discount_amt: The total discount
        discount_type: Percentage, fixed, mix and match, etc
    :return: none
    """

    kind = 'transaction'  # The kind for the new entity
    now = datetime.now()  # Registered datetime

    task_list = []        # Used for bulk upload to datastore

    # Loop over all articles and insert one by one
    for article in articles_querified:
        item = article.get("item_name", 0)
        category_id = fetch_item_category(item)
        if debug:
            print("Assignning category {} to item {}".format(category_id, item))

        # Only happens if we have not seen this item before. Then we add it to
        # unmapped items with an id of -1.
        if category_id == 0:
            cat_task_key = datastore_client.key(DATASTORE_KIND_CATEGORY_ASSIGNMENT, item)
            cat_task = datastore.Entity(key=cat_task_key)
            cat_task["cat_id"] = -1
            datastore_client.put(cat_task)
            print('Saved {}: {}'.format(cat_task.key.name, cat_task['cat_id']))

        # The Cloud Datastore key for the new entity. Creating with partial key
        task_key = datastore_client.key(kind)

        # Prepares the new entity
        task = datastore.Entity(key=task_key)
        task['added_by'] = added_by
        task['cat_id'] = category_id
        task['item_id'] = 0  # Missing
        task['item_name'] = item
        task['price_gross'] = article.get("price_gross", 0)
        task['price_net'] = article.get("price_net", 0)
        task["item_count"] = article.get("item_count", 0)
        task['discount_amt'] = article.get("discount_amt", 0)
        task['discount_type'] = article.get("discount_type", 0)
        task["unit_price_net"] = article.get("unit_price_net", 0)
        task['registered_datetime'] = now
        task['trans_date'] = trans_datetime
        task['receipt_id'] = receipt_id

        if debug:
            print("Writting to datastore:", task)

        # Saves a single entity:
        # datastore_client.put(task)
        task_list.append(task)
        print('Added {}: {}'.format(task.key.name, task['item_name']))

        # End for loop

    # Saves multiple entities at once:
    datastore_client.put_multi(task_list)
