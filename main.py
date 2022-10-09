#!/usr/bin/env python3
import sys
import time
import logging
from display.data import DisplayData
from display.updater import DisplayUpdater
from display.drawer import DisplayDrawer
try:
    import RPi.GPIO as GPIO
    from rpi_epd2in7.epd import EPD
    DISPLAY_TO_EINK = True
except ImportError:
    DISPLAY_TO_EINK = False

try:
    from display.secrets import HA_URL, HA_API_KEY
except (ImportError, AttributeError):
    logging.exception("Uh-oh")
    print("ERROR: Need secrets.py with HA location")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)

# Buttons are BCM pins 29, 31, 33, 35
# GPIO 5, 6, 13, 19


if DISPLAY_TO_EINK:
    epd = EPD()
    epd.init()

    def my_callback(channel):
        print(f"Detected button press, channel {channel}")
    GPIO.setup(5, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(6, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(13, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(19, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(5, GPIO.FALLING, callback=my_callback, bouncetime=200)
    GPIO.add_event_detect(6, GPIO.FALLING, callback=my_callback, bouncetime=200)
    GPIO.add_event_detect(13, GPIO.FALLING, callback=my_callback, bouncetime=200)
    GPIO.add_event_detect(19, GPIO.FALLING, callback=my_callback, bouncetime=200)

    WIDTH = epd.width
    HEIGHT = epd.height
else:
    WIDTH = 176
    HEIGHT = 264

display_data = DisplayData()
updater = DisplayUpdater(display_data, HA_URL, HA_API_KEY)
drawer = DisplayDrawer(display_data, WIDTH, HEIGHT)

while True:
    try:
        updater.update()
        image = drawer.get_image()

        if DISPLAY_TO_EINK:
            logging.info("Displaying to e-ink")
            epd.display_frame(image.rotate(-90, expand=True))
        else:
            logging.info("Showing image")
            image.show()

    except KeyboardInterrupt:
        print("Keyboard interrupt, stopping...")
        break
    except:
        logging.exception("Caught exception during update, will try again later")

    time.sleep(5*60)
