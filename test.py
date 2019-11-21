from google.cloud import vision
import io
import re

# TODO:
# Improve algorithm for allocating word boxes to lines. It could be worth checking the degree of overlap
#   between an item an existing lines. If it is more than x%, allocate it
# Crop image, rotate to keep it completely straight

# Call order:
# response = detect_text(path)
# relevant_lines = article_lines(response)
# receipt_lines = allocate_lines_coop(relevant_lines)
# actual lines = lines_to_text(receipt_lines)

# this controls the threshold for the degree of overlap between an scewed text box and
# the rest of the line for it to be allocated
OVERLAPPING_ALLOCATION_THRESHOLD = 0.3


def crop_and_rotate(path):
    # do some magic here
    # Identify how scewed the image is
    # Rotate it
    return 1


def detect_text(path):
    """Detects text in the file."""
    client = vision.ImageAnnotatorClient.from_service_account_json(
        r"C:\Users\NO007454\Documents\03. Internt\24. Expense analyzer\config_files\Expense analyzer-45b7d2370bbd.json")

    with io.open(path, 'rb') as image_file:
        content = image_file.read()

    image = vision.types.Image(content=content)

    response = client.text_detection(image=image)
    texts = response.text_annotations
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

    for text in response.text_annotations:
        if len(text.description) > 100:
            # Full text, do nothing
            full_text = text.description
        elif "Salgskv" in text.description:
            start_y_coordinate = max(vertex.y for vertex in text.bounding_poly.vertices)
            print("Found starting point at {}, after text {}".format(start_y_coordinate, text.description))
        elif "Totalt" in text.description:
            end_y_coordinate = min(vertex.y for vertex in text.bounding_poly.vertices)
            print("Found ending point at {}, after text {}".format(end_y_coordinate, text.description))

    # Iterate through all lines, extract only those with item y coordinate larger than start and smaller than end
    relevant_items = []
    for text in response.text_annotations:
        if text.bounding_poly.vertices[0].y > start_y_coordinate and text.bounding_poly.vertices[0].y < end_y_coordinate:
            # print("Found an item line!: {}".format(text.description))
            relevant_items.append(text)
    return relevant_items


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

                # Calculate a match % against each other line, to see if picture is slightly squished
                # Calculate against the item to the far right in the current line
                if last_line_item_y1 <= y_first_coor <= last_line_item_y4:
                    # Some overlap detected. item is below the line in comparison
                    overlap_down = float(last_line_item_y4 - y_first_coor) / height
                    print("Found {}% overlap under between text {} and {} on line {}".format(overlap_down, item.description, first_line_item.description, line))

                if last_line_item_y1 <= y_fourth_coor <= last_line_item_y4:
                    # Some overlap detected. item is above the line in comparison
                    overlap_up = float(y_fourth_coor - last_line_item_y1) / height
                    print("Found {}% overlap over between text {} and {} (first item) on line {}".format(overlap_up, item.description, first_line_item.description, line))

                # If any of the matches are above X%, allocate it to that line
                if overlap_down > OVERLAPPING_ALLOCATION_THRESHOLD or overlap_up > OVERLAPPING_ALLOCATION_THRESHOLD:
                    receipt_lines[line].append(item)
                    inserted = True
                    break;

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
    :param receipt_lines: takes a dictionary as input, where the key is a line_id and the value are objects containing the element text and bounding polygon
    :return: A list of text strings concatenated for each line
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
    :return: a list of multiple tuples, consisting of article type, text and price
    """

    price_pattern = "(\d+.\d+)$"
    discont_pattern = ""
    articles = []

    for article in receipt_text:
        print("------------")
        print(article)

        if "rabatt" in article:
            # TODO: x = re.spltt(discount_pattern, article)
            # articles.append(["discount", x[0], x[1]])
            print("Found a discount line")

        elif "antall" in receipt_text:
            # Do something TODO
            print("jadajada")

        elif "artikler" not in article:
            x = re.split(price_pattern, article, 2)

            if len(x) == 3:
                # actual article
                print("len was 3")
                item = x[0]
                price = x[1]
                articles.append([item, price])
            else:
                print("Unparsable line: {}".format(article))
    return articles

# Call order:
# response = detect_text(path)
# relevant_lines = article_lines(response)
# receipt_lines = allocate_lines_coop(relevant_lines)
# actual lines = lines_to_text(receipt_lines)

path = r"C:\Users\NO007454\Documents\03. Internt\24. Expense analyzer\test_images\IMG_1010.JPEG"
path = r"C:\Users\NO007454\Documents\03. Internt\24. Expense analyzer\test_images\IMG_1012.JPEG"
response = detect_text(path)
relevant_lines = article_lines_coop(response)
receipt_lines = allocate_lines_coop(relevant_lines)
actual_lines = lines_to_text(receipt_lines)

counter = 0
for line in actual_lines:
    print("{}: {}".format(counter, line))
    counter += 1

print(query_preparation(actual_lines))
