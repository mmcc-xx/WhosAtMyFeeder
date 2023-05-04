import sqlite3
import numpy as np
from datetime import datetime
import time

import cv2
from tflite_support.task import core
from tflite_support.task import processor
from tflite_support.task import vision
import paho.mqtt.client as mqtt
import hashlib
import yaml

classifier = None
conn = None
config = None
firstmessage = True


def classify(image):

    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    tensor_image = vision.TensorImage.create_from_array(rgb_image)

    categories = classifier.classify(tensor_image)

    return categories.classifications[0].categories


def on_connect(client, userdata, flags, rc):
    print("MQTT Connected")
    #client.subscribe("frigate/birdcam/bird/snapshot")
    client.subscribe(config['frigate']['main_topic'] + "/" +
                     config['frigate']['camera'] + "/" +
                     config['frigate']['object'] + "/" +
                     'snapshot')


def on_disconnect(client, userdata, rc):
    if rc != 0:
        print("Unexpected disconnection, trying to reconnect")
        while True:
            try:
                client.reconnect()
                break
            except Exception as e:
                print(f"Reconnection failed due to {e}, retrying in 60 seconds")
                time.sleep(60)
    else:
        print("Expected disconnection")


def on_message(client, userdata, message):
    global firstmessage
    if not firstmessage:
        np_arr = np.frombuffer(message.payload, dtype=np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        categories = classify(img)
        category = categories[0]
        index = category.index
        score = category.score
        display_name = category.display_name
        category_name = category.category_name

        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d %H:%M:%S")
        result_text = current_time + "\n"
        result_text = result_text + str(category)
        print(result_text)

        if index != 964 and score > config['classification']['threshold']:  # 964 is "background"
            print('Storing...')
            binaryimg = np_arr.tobytes()
            hash_object = hashlib.sha256()
            hash_object.update(binaryimg)
            hash_hex = hash_object.hexdigest()
            cursor = conn.cursor()
            cursor.execute("""  
                 INSERT OR IGNORE INTO detections (detection_time, detection_index, score,
                 display_name, category_name, image, image_hash) VALUES (?, ?, ?, ?, ?, ?, ?)  
                 """, (now, index, score, display_name, category_name, binaryimg, hash_hex))
            conn.commit()

    else:
        firstmessage = False
        print("skipping first message")


def setupdb():
    global conn
    conn = sqlite3.connect("speciesid.db")
    cursor = conn.cursor()
    cursor.execute("""  
        CREATE TABLE IF NOT EXISTS detections (  
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detection_time TIMESTAMP NOT NULL,
            detection_index INTEGER NOT NULL,
            score REAL NOT NULL,
            display_name TEXT NOT NULL,
            category_name TEXT NOT NULL,
            image BLOB NOT NULL,
            image_hash TEXT NOT NULL UNIQUE
        )  
    """)
    conn.commit()


def load_config():
    global config
    file_path = './config/config.yml'
    with open(file_path, 'r') as config_file:
        config = yaml.safe_load(config_file)


def main():

    load_config()

    # Initialize the image classification model
    base_options = core.BaseOptions(
        file_name=config['classification']['model'], use_coral=False, num_threads=4)

    # Enable Coral by this setting
    classification_options = processor.ClassificationOptions(
        max_results=1, score_threshold=0)
    options = vision.ImageClassifierOptions(
        base_options=base_options, classification_options=classification_options)

    # create classifier
    global classifier
    classifier = vision.ImageClassifier.create_from_options(options)

    # setup database
    setupdb()

    client = mqtt.Client("birdspeciesid")
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.on_connect = on_connect
    client.connect(config['frigate']['mqtt_server'])

    client.loop_forever()


if __name__ == '__main__':
    main()
