FROM python:3.9
RUN apt-get update && apt-get install ffmpeg libsm6 libxext6  -y
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY model.tflite .
COPY birdnames.db .
COPY speciesid.py .
COPY webui.py .
COPY queries.py .
COPY util.py .
COPY templates/ ./templates/
COPY static/ ./static/

CMD python ./speciesid.py
