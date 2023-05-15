import sqlite3
import numpy as np
from datetime import datetime
import time
import multiprocessing
import cv2
from tflite_support.task import core
from tflite_support.task import processor
from tflite_support.task import vision
import paho.mqtt.client as mqtt
import hashlib
import yaml
from webui import app
import sys

classifier = None
config = None
firstmessage = True

DBPATH = './data/speciesid.db'


def classify(image):

    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    tensor_image = vision.TensorImage.create_from_array(rgb_image)

    categories = classifier.classify(tensor_image)

    return categories.classifications[0].categories


def on_connect(client, userdata, flags, rc):
    print("MQTT Connected", flush=True)
    for camera in config['frigate']['camera']:
        client.subscribe(config['frigate']['main_topic'] + "/" +
                         camera + "/" +
                         config['frigate']['object'] + "/" +
                         'snapshot')


def on_disconnect(client, userdata, rc):
    if rc != 0:
        print("Unexpected disconnection, trying to reconnect", flush=True)
        while True:
            try:
                client.reconnect()
                break
            except Exception as e:
                print(f"Reconnection failed due to {e}, retrying in 60 seconds", flush=True)
                time.sleep(60)
    else:
        print("Expected disconnection", flush=True)


def on_message(client, userdata, message):
    conn = sqlite3.connect(DBPATH)
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
        print(result_text, flush=True)

        if index != 964 and score > config['classification']['threshold']:  # 964 is "background"
            print('Storing...', flush=True)
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
        print("skipping first message", flush=True)


def setupdb():

    conn = sqlite3.connect(DBPATH)
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

    cursor.execute("""  
        CREATE TABLE IF NOT EXISTS birdnames (  
            id INTEGER PRIMARY KEY AUTOINCREMENT,  
            scientific_name TEXT NOT NULL,  
            common_names TEXT NOT NULL 
        )  
    """)
    conn.commit()


def load_config():
    global config
    file_path = './config/config.yml'
    with open(file_path, 'r') as config_file:
        config = yaml.safe_load(config_file)


def run_webui():
    print("Starting flask app", flush=True)
    app.run(debug=False, host=config['webui']['host'], port=config['webui']['port'])


def run_mqtt_client():
    print("Starting MQTT client. Connecting to: " + config['frigate']['mqtt_server'], flush=True)
    now = datetime.now()
    current_time = now.strftime("%Y%m%d%H%M%S")
    client = mqtt.Client("birdspeciesid" + current_time)
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.on_connect = on_connect
    # check if we are using authentication and set username/password if so
    if config['frigate']['mqtt_auth']:
        username = config['frigate']['mqtt_username']
        password = config['frigate']['mqtt_password']
        client.username_pw_set(username, password)

    client.connect(config['frigate']['mqtt_server'])
    client.loop_forever()


def main():

    now = datetime.now()
    current_time = now.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

    print("Time: " + current_time, flush=True)
    print("Python version", flush=True)
    print(sys.version, flush=True)
    print("Version info.", flush=True)
    print(sys.version_info, flush=True)

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
    print("Starting threads for Flask and MQTT", flush=True)
    flask_process = multiprocessing.Process(target=run_webui)
    mqtt_process = multiprocessing.Process(target=run_mqtt_client)

    flask_process.start()
    mqtt_process.start()

    flask_process.join()
    mqtt_process.join()


if __name__ == '__main__':
    print("Calling Main", flush=True)
    main()
