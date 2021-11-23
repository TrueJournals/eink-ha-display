from .data import DisplayData
import requests
import logging
import datetime


logger = logging.getLogger(__name__)


class DisplayUpdater:
    def __init__(self, data: DisplayData, ha_url: str, ha_api_key: str):
        self.data = data
        self.ha_url = ha_url

        self._session = requests.Session()
        self._session.headers['Authorization'] = f"Bearer {ha_api_key}"

    def update(self):
        self._get_electric_cost()
        self._get_forecast()
        self._get_daily_low_high()
        self._get_daily_energy_usage()

    def _get_electric_cost(self):
        r = self._session.get(f"{self.ha_url}/states/sensor.comed_5_minute_price")
        if r.status_code == requests.codes.ok:
            self.data.electric_cost = float(r.json()['state'])
        else:
            logger.warning("Couldn't get electric price -- %d", r.status_code)

    def _get_forecast(self):
        r = self._session.get(f"{self.ha_url}/states/weather.kpwk_hourly")
        if r.status_code == requests.codes.ok:
            data = r.json()['attributes']['forecast']
            self.data.forecast = data[:3]
        else:
            logger.warning("Couldn't get forecast info -- %d", r.status_code)

    def _get_daily_low_high(self):
        r = self._session.get(f"{self.ha_url}/states/weather.kpwk_daynight")
        if r.status_code == requests.codes.ok:
            data = r.json()['attributes']['forecast']
            today = datetime.datetime.today()
            for point in (0, 1):
                if datetime.datetime.fromisoformat(data[point]['datetime']).date() == datetime.datetime.today().date():
                    if data[point]['daytime']:
                        self.data.day_lowhigh[1] = data[point]['temperature']
                        self.data.day_lowhigh_date = today
                    else:
                        self.data.day_lowhigh[0] = data[point]['temperature']
                        self.data.day_lowhigh_date = today
        else:
            logger.warning("Couldn't get daynight info -- %d", r.status_code)

    def _get_daily_energy_usage(self):
        # TODO: Switch to websocket API to use statistics_during_period?
        today = datetime.date.today()
        r = self._session.get(f"{self.ha_url}/history/period/{today.isoformat()}T00:00:00-06:00", params={  # TODO: Timezone
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
            self.data.daily_energy = energy_sum
        else:
            logger.warning("Couldn't get energy usage -- %d", r.status_code)
