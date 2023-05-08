from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import base64
from datetime import datetime
import yaml
from EcoNameTranslator import to_common

app = Flask(__name__)
config = None


def format_datetime(value, format='%B %d, %Y %H:%M:%S'):
    dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S.%f')  # Adjusted input format to include microseconds
    return dt.strftime(format)


app.jinja_env.filters['datetime'] = format_datetime


def get_common_names(scientific_name):
    conn = sqlite3.connect('speciesid.db')
    cursor = conn.cursor()

    # Look up the scientific name in the birdnames table
    cursor.execute("SELECT common_names FROM birdnames WHERE scientific_name = ?;", (scientific_name,))
    row = cursor.fetchone()

    if row:
        # If the scientific name is found, return the common names from the table
        common_names_str = row[0]
        common_names = common_names_str.split(',')
    else:
        # If the scientific name is not found, use the to_common() function to get the common names
        common_names = to_common([scientific_name])[scientific_name][1]

        # Store the common names in the birdnames table for faster access later
        common_names_str = ','.join(common_names)
        cursor.execute("INSERT INTO birdnames (scientific_name, common_names) VALUES (?, ?);",
                       (scientific_name, common_names_str))
        conn.commit()

    conn.close()
    return common_names


def get_bird_record(record_id):
    # Connect to the SQLite database
    conn = sqlite3.connect('speciesid.db')
    cursor = conn.cursor()

    # Query the detections table to get the bird record by id
    cursor.execute("SELECT * FROM detections WHERE id=?", (record_id,))
    bird_record = cursor.fetchone()

    # Get the common names using the get_common_names function
    display_name = bird_record[4]
    common_names = get_common_names(display_name)

    # Close the connection
    cursor.close()
    conn.close()

    return bird_record, common_names


def get_most_recent_detections(limit=50):
    conn = sqlite3.connect("speciesid.db")
    cursor = conn.cursor()

    cursor.execute("""  
        SELECT *  
        FROM detections  
        ORDER BY detection_time DESC  
        LIMIT ?  
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    commonnames = []
    for row in rows:
        scientificname = row[4]
        commonname = get_common_names(scientificname)
        commonnames.append(commonname)

    return rows, commonnames


def frequencies_by_date(date, sort_order):
    conn = sqlite3.connect("speciesid.db")
    cursor = conn.cursor()

    query = """  
        SELECT category_name, display_name, COUNT(*) as frequency, MAX(score) as max_score  
        FROM detections  
        WHERE date(detection_time) = ?  
        GROUP BY category_name  
        ORDER BY frequency {}  
    """.format(sort_order)

    cursor.execute(query, (date,))
    rows = cursor.fetchall()

    images = []
    commonnames = []
    record_ids = []
    for row in rows:
        cursor.execute("""  
            SELECT image, id  
            FROM detections  
            WHERE category_name = ? AND score = ? AND date(detection_time) = ?  
        """, (row[0], row[3], date))

        returneddata = cursor.fetchone()
        image_data = returneddata[0]
        images.append(base64.b64encode(image_data).decode("utf-8"))
        scientificname = row[1]
        commonname = get_common_names(scientificname)

        # This should be the list of common names associated with the sciency name
        commonnames.append(commonname)
        record_ids.append(returneddata[1])
    conn.close()
    return rows, images, commonnames, record_ids


def get_min_date():
    conn = sqlite3.connect("speciesid.db")
    cur = conn.cursor()
    cur.execute("SELECT MIN(date(detection_time)) FROM detections")
    min_date = cur.fetchone()[0]
    conn.close()
    return min_date


@app.route('/mostrecent')
def recent_records():
    records, commonnames = get_most_recent_detections()
    for i, record in enumerate(records):
        # Encode the image as base64 for embedding in the HTML
        records[i] = list(record)
        records[i][6] = base64.b64encode(record[6]).decode("utf-8")
    zipped_data = zip(records, commonnames)
    return render_template('most_recent.html', zipped_data=zipped_data)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        date = request.form['date']
        sort_order = request.form['sort_order']
        return redirect(url_for('results', date=date, sort_order=sort_order))

    min_date = get_min_date()
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('index.html', today=today, min_date=min_date)


@app.route('/results')
def results():
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    sort_order = request.args.get('sort_order', 'DESC')
    data, images, commonnames, record_ids = frequencies_by_date(date, sort_order)
    zipped_data = zip(data, images, commonnames, record_ids)
    return render_template('results.html', zipped_data=zipped_data, date=date, sort_order=sort_order)


@app.route('/display_images/<date>/<fancy_name>')
def display_images(date, fancy_name):
    conn = sqlite3.connect('speciesid.db')
    cur = conn.cursor()

    # Convert date string to datetime object
    date_obj = datetime.strptime(date, '%Y-%m-%d')

    # Get images, timestamps, and scores for the specified date and fancy_name
    cur.execute(
        "SELECT image, detection_time, score, id FROM detections WHERE date(detection_time) = ? AND display_name = ?",
        (date_obj.date(), fancy_name))
    images = [(row[0], row[1], row[2], row[3]) for row in cur.fetchall()]

    conn.close()
    for i, image in enumerate(images):
        images[i] = list(image)
        images[i][0] = base64.b64encode(image[0]).decode("utf-8")

    return render_template('image_grid.html', date=date, fancy_name=fancy_name, images=images)


@app.route('/bird/<int:record_id>')
def bird_details(record_id):
    # Fetch the bird record based on the record_id
    # You will need to implement get_bird_record function to fetch the record from your data
    bird_record, common_names = get_bird_record(record_id)
    bird_record = list(bird_record)
    bird_record[6] = base64.b64encode(bird_record[6]).decode("utf-8")

    return render_template('bird_details.html', bird_record=bird_record, common_names=common_names)


def load_config():
    global config
    file_path = './config/config.yml'
    with open(file_path, 'r') as config_file:
        config = yaml.safe_load(config_file)


#if __name__ == '__main__':
    #load_config()
    #app.run(debug=True, host=config['webui']['host'], port=config['webui']['port'])
