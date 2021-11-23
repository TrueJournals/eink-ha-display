from .data import DisplayData
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import cairosvg
import math
import datetime
import json
import logging


logger = logging.getLogger(__name__)


def load_icon(filename, width=None, height=None):
    with BytesIO() as out:
        cairosvg.svg2png(url=f"icons/{filename}", write_to=out, background_color="white", output_width=width, output_height=height)
        im = Image.open(out)
        im.load()
        return im


class DisplayDrawer:
    def __init__(self, data: DisplayData, width: int, height: int):
        self.data = data
        self._load_static_data()
        self.width = width
        self.height = height

    def _load_static_data(self):
        self._font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16)
        self._icon_lightning = load_icon("lightning-bolt.svg")
        self._icon_thermo_high = load_icon("thermometer-chevron-up.svg")
        self._icon_thermo_low = load_icon("thermometer-chevron-down.svg")
        self._icon_home_energy = load_icon("home-lightning-bolt.svg")

        with open("icons-meta.json", "r") as f:
            self._icons = json.load(f)

    def _get_icon(self, weather):
        for icon in self._icons:
            if icon['name'] == weather or icon['name']  == f"weather-{weather}":
                return icon["name"]
            if weather in icon['aliases'] or f"weather-{weather}" in icon['aliases']:
                return icon["name"]
        return None

    def get_image(self):
        logger.info("Drawing image...")
        image = Image.new('1', (self.height, self.width), 255)
        draw = ImageDraw.Draw(image)

        x_pos = 5
        x_pos = self._draw_low_temperature(image, draw, x_pos)
        x_pos = self._draw_high_temperature(image, draw, x_pos)

        x_pos = 13
        x_pos = self._draw_forecast(image, draw, x_pos)

        x_pos = 0
        x_pos = self._draw_electric_cost(image, draw, x_pos)
        x_pos = self._draw_energy_usage(image, draw, x_pos)

        logger.info("Done")
        return image

    def _draw_low_temperature(self, image, draw, x_pos):
        image.paste(self._icon_thermo_low, (x_pos, 2))
        x_pos += 25
        low_temp = "--" if math.isnan(self.data.day_lowhigh[0]) else self.data.day_lowhigh[0]
        draw.text((x_pos, 5), f"{low_temp}°", font=self._font, fill=0)
        x_pos += int(draw.textlength(f"{low_temp}°", font=self._font))
        x_pos += 10
        return x_pos

    def _draw_high_temperature(self, image, draw, x_pos):
        image.paste(self._icon_thermo_high, (x_pos, 2))
        x_pos += 25
        high_temp = "--" if math.isnan(self.data.day_lowhigh[1]) else self.data.day_lowhigh[1]
        draw.text((x_pos, 5), f"{high_temp}°", font=self._font, fill=0)
        x_pos += int(draw.textlength(f"{high_temp}°", font=self._font))
        return x_pos

    def _draw_forecast(self, image, draw, x_pos):
        for hour in self.data.forecast:
            forecast_time = datetime.datetime.fromisoformat(hour['datetime'])
            try:
                draw.rounded_rectangle(((x_pos, 30), (x_pos + 70, 120)), 7)
            except AttributeError:
                draw.rectangle(((x_pos, 30), (x_pos + 70, 120)))
            draw.text((x_pos + (70/2), 32), f"{forecast_time:%l %p}", font=self._font, fill=0, anchor="ma")
            draw.text((x_pos + 3 + (70/2), 120), f"{hour['temperature']}°", font=self._font, fill=0, anchor="md")
            icon = self._get_icon(hour['condition'])
            if icon is not None:
                icon_image = load_icon(f"{icon}.svg", 50, 50)
                image.paste(icon_image, (int(x_pos+(70/2)-(50/2)), 50))
            else:
                logger.warning("Couldn't find image for %s", hour['condition'])

            x_pos += 82

        return x_pos

    def _draw_electric_cost(self, image, draw, x_pos):
        image.paste(self._icon_lightning, (x_pos, 130))
        x_pos += 22
        draw.text((x_pos, 133), f"{self.data.electric_cost:.1f}¢", font=self._font, fill=0)
        x_pos += int(draw.textlength(f"{self.data.electric_cost:.1f}¢", font=self._font))
        x_pos += 10
        return x_pos

    def _draw_energy_usage(self, image, draw, x_pos):
        image.paste(self._icon_home_energy, (x_pos, 130))
        x_pos += 25
        draw.text((x_pos, 133), f"{self.data.daily_energy:.2f} kWh", font=self._font, fill=0)
        x_pos += int(draw.textlength(f"{self.data.daily_energy:.2f} kWh", font=self._font))
        x_pos += 10
        return x_pos
