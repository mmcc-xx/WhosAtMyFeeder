# Who's At My Feeder?

![screenshot](screenshot.jpg)

This app works with [Frigate](https://frigate.video/) to identify the species of
the birds that Frigate detects.

To make it go, set up Frigate to detect the 'bird' object in a video stream, and
to send out snapshots. 

Then download this repository.

`git clone https://github.com/mmcc-xx/WhosAtMyFeeder.git`

Then go into the directory that was created and
download the tflite model from here: https://tfhub.dev/google/lite-model/aiy/vision/classifier/birds_V1/3

Rename it to model.tflite

Then build the docker image...

` docker build -t whosatmyfeeder .`

Then edit the values in config\config.yml to reflect your installation.

Take a look at docker-compose.yml and make any changes that might be needed, like
the timezone.

Finally, fire it up with `docker-compose up -d` If you used the default config file
and docker-compose file you should be able to access the web UI on http://127.0.0.1:7766
or on http://yourserveraddress:7766

## To Do...
- Put it on Docker Hub
