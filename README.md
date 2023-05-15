# Who's At My Feeder?

![screenshot](screenshot.jpg)

This app works with [Frigate](https://frigate.video/) to identify the species of
the birds that Frigate detects.

To make it go, set up Frigate to detect the 'bird' object in a video stream, and
to send out snapshots. 

Then, on the machine where you want to run this app, create a new directory. Copy
the docker-compose.yml file from here into that directory. Take a quick peek
at that file and make any changes that might be needed, like the timezone.

In your directory, make a directory called config, and copy config/config.yml from here
into your config directory. Edit it to make changes for your setup. You can add the names
of multiple cameras to the camera array. The model is already
in the image, so unless you want to use a different model, no need to change the
model name.

Also make a directory called data. The database will be created there.

Finally, fire it up with `docker-compose up -d` If you used the default config file
and docker-compose file you should be able to access the web UI on http://127.0.0.1:7766
or on http://yourserveraddress:7766

The image is on Docker Hub at https://hub.docker.com/r/mmcc73/whosatmyfeeder