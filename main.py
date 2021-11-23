#!/usr/bin/env python3
import sys
import math
import time
import requests
from PIL import Image, ImageDraw, ImageFont
import logging
import datetime
import json
import cairosvg
from io import BytesIO
from display.data import DisplayData
import pprint
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


with open("icons-meta.json", "r") as f:
    icons = json.load(f)


def get_icon(weather):
    for icon in icons:
        if icon['name'] == weather or icon['name']  == f"weather-{weather}":
            return icon["name"]
        if weather in icon['aliases'] or f"weather-{weather}" in icon['aliases']:
            return icon["name"]
    return None


def load_icon(filename, width=None, height=None):
    with BytesIO() as out:
        cairosvg.svg2png(url=f"icons/{filename}", write_to=out, background_color="white", output_width=width, output_height=height)
        im = Image.open(out)
        im.load()
        return im


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

image = Image.new('1', (HEIGHT, WIDTH), 255)
draw = ImageDraw.Draw(image)
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16)

s = requests.Session()
s.headers['Authorization'] = f"Bearer {HA_API_KEY}"

display_data = DisplayData()

# Get electric cost
r = s.get(f"{HA_URL}/states/sensor.comed_5_minute_price")
if r.status_code == requests.codes.ok:
    display_data.electric_cost = float(r.json()['state'])
else:
    logging.warning("Couldn't get electric price -- %d", r.status_code)

# Get forecasts
r = s.get(f"{HA_URL}/states/weather.kpwk_hourly")
if r.status_code == requests.codes.ok:
    data = r.json()['attributes']['forecast']
    display_data.forecast = data[:3]
else:
    logging.warning("Couldn't get forecast info -- %d", r.status_code)

# Get daily high/low
r = s.get(f"{HA_URL}/states/weather.kpwk_daynight")
if r.status_code == requests.codes.ok:
    data = r.json()['attributes']['forecast']
    today = datetime.datetime.today()
    for point in (0, 1):
        if datetime.datetime.fromisoformat(data[point]['datetime']).date() == datetime.datetime.today().date():
            if data[point]['daytime']:
                display_data.day_lowhigh[1] = data[point]['temperature']
                display_data.day_lowhigh_date = today
            else:
                display_data.day_lowhigh[0] = data[point]['temperature']
                display_data.day_lowhigh_date = today
else:
    logging.warning("Couldn't get daynight info -- %d", r.status_code)

# Get daily energy usage
# TODO: Switch to websocket API to use statistics_during_period?
today = datetime.date.today()
r = s.get(f"{HA_URL}/history/period/{today.isoformat()}T00:00:00-06:00", params={  # TODO: Timezone
    "filter_entity_id": "sensor.home_energy_meter_gen5_electric_consumed_kwh",
    "minimal_response": ""
})
if r.status_code == requests.codes.ok:
    data = r.json()[0]
    energy_sum = 0
    for previous, current in zip(data, data[1:]):
        if float(current['state']) > float(previous['state']):
            energy_sum += float(current['state']) - float(previous['state'])
        else:
            energy_sum += float(current['state'])  # Assumes there was a reset to zero
    display_data.daily_energy = energy_sum
else:
    logging.warning("Couldn't get energy usage -- %d", r.status_code)


icon_lightning = load_icon("lightning-bolt.svg")
icon_thermo_high = load_icon("thermometer-chevron-up.svg")
icon_thermo_low = load_icon("thermometer-chevron-down.svg")
icon_home_energy = load_icon("home-lightning-bolt.svg")

x_pos = 5

# Low temperature
image.paste(icon_thermo_low, (x_pos, 2))
x_pos += 25
low_temp = "--" if math.isnan(display_data.day_lowhigh[0]) else display_data.day_lowhigh[0]
draw.text((x_pos, 5), f"{low_temp}°", font=font, fill=0)
x_pos += int(draw.textlength(f"{low_temp}°", font=font))
x_pos += 10

# High temperature
image.paste(icon_thermo_high, (x_pos, 2))
x_pos += 25
high_temp = "--" if math.isnan(display_data.day_lowhigh[1]) else display_data.day_lowhigh[1]
draw.text((x_pos, 5), f"{high_temp}°", font=font, fill=0)
x_pos += int(draw.textlength(f"{high_temp}°", font=font))

# Forecast, next three hours
x_pos = 13
for hour in display_data.forecast:
    forecast_time = datetime.datetime.fromisoformat(hour['datetime'])
    try:
        draw.rounded_rectangle(((x_pos, 30), (x_pos + 70, 120)), 7)
    except AttributeError:
        draw.rectangle(((x_pos, 30), (x_pos + 70, 120)))
    draw.text((x_pos + (70/2), 32), f"{forecast_time:%l %p}", font=font, fill=0, anchor="ma")
    draw.text((x_pos + 3 + (70/2), 120), f"{hour['temperature']}°", font=font, fill=0, anchor="md")
    icon = get_icon(hour['condition'])
    if icon is not None:
        icon_image = load_icon(f"{icon}.svg", 50, 50)
        image.paste(icon_image, (int(x_pos+(70/2)-(50/2)), 50))
    else:
        logging.warning("Couldn't find image for %s", hour['condition'])

    x_pos += 82

x_pos = 0

# Current electric cost
image.paste(icon_lightning, (x_pos, 130))
x_pos += 22
draw.text((x_pos, 133), f"{display_data.electric_cost:.1f}¢", font=font, fill=0)
x_pos += int(draw.textlength(f"{display_data.electric_cost:.1f}¢", font=font))

# Home energy Usage
x_pos += 10
image.paste(icon_home_energy, (x_pos, 130))
x_pos += 25
draw.text((x_pos, 133), f"{display_data.daily_energy:.2f} kWh", font=font, fill=0)
x_pos += int(draw.textlength(f"{display_data.daily_energy:.2f} kWh", font=font))


if DISPLAY_TO_EINK:
    epd.display_frame(image.rotate(-90, expand=True))
else:
    image.show()
