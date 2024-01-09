import json
import multiprocessing
import sqlite3
import sys
import time
from datetime import datetime
from io import BytesIO

import numpy as np
import paho.mqtt.client as mqtt
import requests
from PIL import Image, ImageOps
from tflite_support.task import core, processor, vision

from queries import get_common_name
from util import load_config
from webui import app

classifier = None
config = load_config()
firstmessage = True

DBPATH = config["database"]["path"]


def classify(image):
    tensor_image = vision.TensorImage.create_from_array(image)

    categories = classifier.classify(tensor_image)

    return categories.classifications[0].categories


def on_connect(client, userdata, flags, rc):
    print("MQTT Connected", flush=True)

    # we are going subscribe to frigate/events and look for bird detections there
    client.subscribe(config["frigate"]["main_topic"] + "/events")


def on_disconnect(client, userdata, rc):
    if rc != 0:
        print("Unexpected disconnection, trying to reconnect", flush=True)
        while True:
            try:
                client.reconnect()
                break
            except Exception as e:
                print(
                    f"Reconnection failed due to {e}, retrying in 60 seconds",
                    flush=True,
                )
                time.sleep(60)
    else:
        print("Expected disconnection", flush=True)


def set_sublabel(frigate_url, frigate_event, sublabel):
    post_url = frigate_url + "/api/events/" + frigate_event + "/sub_label"

    # frigate limits sublabels to 20 characters currently
    if len(sublabel) > 20:
        sublabel = sublabel[:20]

        # Create the JSON payload
    payload = {"subLabel": sublabel}

    # Set the headers for the request
    headers = {"Content-Type": "application/json"}

    # Submit the POST request with the JSON payload
    response = requests.post(post_url, data=json.dumps(payload), headers=headers)

    # Check for a successful response
    if response.status_code == 200:
        print("Sublabel set successfully to: " + sublabel, flush=True)
    else:
        print("Failed to set sublabel. Status code:", response.status_code, flush=True)


def on_message(client, userdata, message):
    conn = sqlite3.connect(DBPATH)

    global firstmessage
    if not firstmessage:
        # Convert the MQTT payload to a Python dictionary
        payload_dict = json.loads(message.payload)

        # Extract the 'after' element data and store it in a dictionary
        after_data = payload_dict.get("after", {})

        if (
            after_data["camera"] in config["frigate"]["camera"]
            and after_data["label"] == "bird"
        ):
            frigate_event = after_data["id"]
            frigate_url = config["frigate"]["frigate_url"]
            snapshot_url = (
                frigate_url + "/api/events/" + frigate_event + "/snapshot.jpg"
            )

            print("Getting image for event: " + frigate_event, flush=True)
            print("Here's the URL: " + snapshot_url, flush=True)
            # Send a GET request to the snapshot_url
            params = {"crop": 1, "quality": 95}
            response = requests.get(snapshot_url, params=params)
            # Check if the request was successful (HTTP status code 200)
            if response.status_code == 200:
                # Open the image from the response content and convert it to a NumPy array
                image = Image.open(BytesIO(response.content))

                file_path = "fullsized.jpg"  # Change this to your desired file path
                image.save(
                    file_path, format="JPEG"
                )  # You can change the format if needed

                # Resize the image while maintaining its aspect ratio
                max_size = (224, 224)
                image.thumbnail(max_size)

                # Pad the image to fill the remaining space
                padded_image = ImageOps.expand(
                    image,
                    border=(
                        (max_size[0] - image.size[0]) // 2,
                        (max_size[1] - image.size[1]) // 2,
                    ),
                    fill="black",
                )  # Change the fill color if necessary

                file_path = "shrunk.jpg"  # Change this to your desired file path
                padded_image.save(
                    file_path, format="JPEG"
                )  # You can change the format if needed

                np_arr = np.array(padded_image)

                categories = classify(np_arr)
                category = categories[0]
                index = category.index
                score = category.score
                display_name = category.display_name
                category_name = category.category_name

                start_time = datetime.fromtimestamp(after_data["start_time"])
                formatted_start_time = start_time.strftime("%Y-%m-%d %H:%M:%S")
                result_text = formatted_start_time + "\n"
                result_text = result_text + str(category)
                print(result_text, flush=True)

                if (
                    index != 964 and score > config["classification"]["threshold"]
                ):  # 964 is "background"
                    cursor = conn.cursor()

                    # Check if a record with the given frigate_event exists
                    cursor.execute(
                        "SELECT * FROM detections WHERE frigate_event = ?",
                        (frigate_event,),
                    )
                    result = cursor.fetchone()

                    if result is None:
                        # Insert a new record if it doesn't exist
                        print("No record yet for this event. Storing.", flush=True)
                        cursor.execute(
                            """  
                            INSERT INTO detections (detection_time, detection_index, score,  
                            display_name, category_name, frigate_event, camera_name) VALUES (?, ?, ?, ?, ?, ?, ?)  
                            """,
                            (
                                formatted_start_time,
                                index,
                                score,
                                display_name,
                                category_name,
                                frigate_event,
                                after_data["camera"],
                            ),
                        )
                        # set the sublabel
                        set_sublabel(
                            frigate_url, frigate_event, get_common_name(display_name)
                        )
                    else:
                        print(
                            "There is already a record for this event. Checking score",
                            flush=True,
                        )
                        # Update the existing record if the new score is higher
                        existing_score = result[3]
                        if score > existing_score:
                            print(
                                "New score is higher. Updating record with higher score.",
                                flush=True,
                            )
                            cursor.execute(
                                """  
                                UPDATE detections  
                                SET detection_time = ?, detection_index = ?, score = ?, display_name = ?, category_name = ?  
                                WHERE frigate_event = ?  
                                """,
                                (
                                    formatted_start_time,
                                    index,
                                    score,
                                    display_name,
                                    category_name,
                                    frigate_event,
                                ),
                            )
                            # set the sublabel
                            set_sublabel(
                                frigate_url,
                                frigate_event,
                                get_common_name(display_name),
                            )
                        else:
                            print("New score is lower.", flush=True)

                    # Commit the changes
                    conn.commit()

            else:
                print(
                    f"Error: Could not retrieve the image. Status code: {response.status_code}",
                    flush=True,
                )

    else:
        firstmessage = False
        print("skipping first message", flush=True)

    conn.close()


def setupdb():
    conn = sqlite3.connect(DBPATH)
    cursor = conn.cursor()
    cursor.execute(
        """    
        CREATE TABLE IF NOT EXISTS detections (    
            id INTEGER PRIMARY KEY AUTOINCREMENT,  
            detection_time TIMESTAMP NOT NULL,  
            detection_index INTEGER NOT NULL,  
            score REAL NOT NULL,  
            display_name TEXT NOT NULL,  
            category_name TEXT NOT NULL,  
            frigate_event TEXT NOT NULL UNIQUE,
            camera_name TEXT NOT NULL 
        )    
    """
    )
    conn.commit()

    conn.close()


def run_webui():
    print("Starting flask app", flush=True)
    app.run(debug=False, host=config["webui"]["host"], port=config["webui"]["port"])


def run_mqtt_client():
    print(
        "Starting MQTT client. Connecting to: " + config["frigate"]["mqtt_server"],
        flush=True,
    )
    now = datetime.now()
    current_time = now.strftime("%Y%m%d%H%M%S")
    client = mqtt.Client("birdspeciesid" + current_time)
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.on_connect = on_connect
    # check if we are using authentication and set username/password if so
    if config["frigate"]["mqtt_auth"]:
        username = config["frigate"]["mqtt_username"]
        password = config["frigate"]["mqtt_password"]
        client.username_pw_set(username, password)

    client.connect(config["frigate"]["mqtt_server"])
    client.loop_forever()


def main():
    now = datetime.now()
    current_time = now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    print("Time: " + current_time, flush=True)
    print("Python version", flush=True)
    print(sys.version, flush=True)
    print("Version info.", flush=True)
    print(sys.version_info, flush=True)

    # Initialize the image classification model
    base_options = core.BaseOptions(
        file_name=config["classification"]["model"], use_coral=False, num_threads=4
    )

    # Enable Coral by this setting
    classification_options = processor.ClassificationOptions(
        max_results=1, score_threshold=0
    )
    options = vision.ImageClassifierOptions(
        base_options=base_options, classification_options=classification_options
    )

    # create classifier
    global classifier
    classifier = vision.ImageClassifier.create_from_options(options)

    # setup database
    setupdb()
    print("Starting threads for Flask and MQTT", flush=True)
    flask_process = multiprocessing.Process(target=run_webui)
    mqtt_process = multiprocessing.Process(target=run_mqtt_client)

    flask_process.start()
    mqtt_process.start()

    flask_process.join()
    mqtt_process.join()


if __name__ == "__main__":
    print("Calling Main", flush=True)
    main()
