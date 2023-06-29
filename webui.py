import os
from datetime import datetime

import requests
import yaml
from flask import Flask, abort, render_template, send_file, send_from_directory

from queries import (get_common_name, get_daily_summary,
                     get_earliest_detection_date, get_records_for_date_hour,
                     get_records_for_scientific_name_and_date,
                     recent_detections)

app = Flask(__name__)
config = None
DBPATH = "./data/speciesid.db"
NAMEDBPATH = "./birdnames.db"


def format_datetime(value, format="%B %d, %Y %H:%M:%S"):
    dt = datetime.strptime(
        value, "%Y-%m-%d %H:%M:%S.%f"
    )  # Adjusted input format to include microseconds
    return dt.strftime(format)


app.jinja_env.filters["datetime"] = format_datetime


@app.route("/")
def index():
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    earliest_date = get_earliest_detection_date()
    recent_records = recent_detections(5)
    daily_summary = get_daily_summary(today)
    return render_template(
        "index.html",
        recent_detections=recent_records,
        daily_summary=daily_summary,
        current_hour=today.hour,
        date=date_str,
        earliest_date=earliest_date,
    )


@app.route("/frigate/<frigate_event>/thumbnail.jpg")
def frigate_thumbnail(frigate_event):
    frigate_url = config["frigate"]["frigate_url"]
    try:
        response = requests.get(
            f"{frigate_url}/api/events/{frigate_event}/thumbnail.jpg", stream=True
        )

        if response.status_code == 200:
            return send_file(response.raw, mimetype=response.headers["Content-Type"])
        else:
            # Return the single transparent pixel image from the local file if the actual image is not found
            return send_from_directory("static/images", "1x1.png", mimetype="image/png")
    except Exception as e:
        print(f"Error fetching image from frigate: {e}", flush=True)
        abort(500)


@app.route("/frigate/<frigate_event>/snapshot.jpg")
def frigate_snapshot(frigate_event):
    frigate_url = config["frigate"]["frigate_url"]
    try:
        # Fetch the image from frigate
        print("Getting snapshot from Frigate", flush=True)
        response = requests.get(
            f"{frigate_url}/api/events/{frigate_event}/snapshot.jpg", stream=True
        )

        if response.status_code == 200:
            # Serve the image to the client using Flask's send_file()
            return send_file(response.raw, mimetype=response.headers["Content-Type"])
        else:
            # Return the single transparent pixel image from the local file if the actual image is not found
            return send_from_directory("static/images", "1x1.png", mimetype="image/png")
    except Exception as e:
        # If there's any issue fetching the image, return a 500 error
        print(f"Error fetching image from frigate: {e}", flush=True)
        abort(500)


@app.route("/frigate/<frigate_event>/clip.mp4")
def frigate_clip(frigate_event):
    frigate_url = config["frigate"]["frigate_url"]
    try:
        # Fetch the clip from frigate
        print("Getting snapshot from Frigate", flush=True)
        response = requests.get(
            f"{frigate_url}/api/events/{frigate_event}/clip.mp4", stream=True
        )

        if response.status_code == 200:
            # Serve the image to the client using Flask's send_file()
            return send_file(response.raw, mimetype=response.headers["Content-Type"])
        else:
            # Return the single transparent pixel image from the local file if the actual image is not found
            return send_from_directory("static/images", "1x1.png", mimetype="image/png")
    except Exception as e:
        # If there's any issue fetching the image, return a 500 error
        print(f"Error fetching clip from frigate: {e}", flush=True)
        abort(500)


@app.route("/detections/by_hour/<date>/<int:hour>")
def show_detections_by_hour(date, hour):
    records = get_records_for_date_hour(date, hour)
    return render_template(
        "detections_by_hour.html", date=date, hour=hour, records=records
    )


@app.route(
    "/detections/by_scientific_name/<scientific_name>/<date>",
    defaults={"end_date": None},
)
@app.route("/detections/by_scientific_name/<scientific_name>/<date>/<end_date>")
def show_detections_by_scientific_name(scientific_name, date, end_date):
    if end_date is None:
        records = get_records_for_scientific_name_and_date(scientific_name, date)
        return render_template(
            "detections_by_scientific_name.html",
            scientific_name=scientific_name,
            date=date,
            end_date=end_date,
            common_name=get_common_name(scientific_name),
            records=records,
        )


@app.route("/daily_summary/<date>")
def show_daily_summary(date):
    date_datetime = datetime.strptime(date, "%Y-%m-%d")
    daily_summary = get_daily_summary(date_datetime)
    today = datetime.now().strftime("%Y-%m-%d")
    earliest_date = get_earliest_detection_date()
    return render_template(
        "daily_summary.html",
        daily_summary=daily_summary,
        date=date,
        today=today,
        earliest_date=earliest_date,
    )


def load_config():
    global config
    file_path = os.getenv("CONFIG_PATH", "./config/config.yml")
    with open(file_path, "r") as config_file:
        config = yaml.safe_load(config_file)
    return config


load_config()
