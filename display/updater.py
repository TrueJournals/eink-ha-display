from .data import DisplayData
import requests
import logging
import datetime
import websockets
import websockets.sync.client
import pprint
import json


logger = logging.getLogger(__name__)


class TimeoutSession(requests.Session):
    def __init__(self, timeout=(3.05, 4)):
        self.timeout = timeout
        return super().__init__()

    def request(self, *args, **kwargs):
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.timeout

        return super().request(*args, **kwargs)


class DisplayUpdater:
    def __init__(self, data: DisplayData, ha_url: str, ha_api_key: str):
        self.data = data
        self.ha_url = ha_url
        self._id = 0

        self.__api_key = ha_api_key
        self._session = TimeoutSession()
        self._session.headers['Authorization'] = f"Bearer {ha_api_key}"

    def _get_id(self):
        self._id += 1
        return self._id

    def _call_service(self, ws: websockets.WebSocketClientProtocol, domain: str, service: str, target: str, response: bool, service_data):
        _id = self._get_id()
        ws.send(json.dumps({
            "id": _id,
            "type": "call_service",
            "domain": domain,
            "service": service,
            "service_data": service_data,
            "target": {
                "entity_id": target
            },
            "return_response": response
        }))
        msg = {}
        while "id" not in msg or msg["id"] != _id:
            msg = json.loads(ws.recv())

        return msg

    def update(self):
        logger.info("Updating display data...")
        with websockets.sync.client.connect(f"{self.ha_url.replace('http', 'ws')}/websocket") as ws:
            self._authorize_to_websocket(ws)
            self._get_forecast(ws)
            self._get_daily_low_high(ws)
        self._get_electric_cost()
        self._get_daily_energy_usage()
        self._get_soil_moisture()
        logger.info("Done")

    def _authorize_to_websocket(self, ws: websockets.WebSocketClientProtocol):
        auth_msg = json.loads(ws.recv())
        pprint.pprint(auth_msg)
        if "type" not in auth_msg or auth_msg["type"] != "auth_required":
            logger.warning("Didn't get an auth request")
            raise RuntimeError("Didn't get auth request")

        ws.send(json.dumps({
            "type": "auth",
            "access_token": self.__api_key
        }))
        msg = json.loads(ws.recv())
        if msg["type"] != "auth_ok":
            raise RuntimeError("Failed to auth to HA")

    def _get_soil_moisture(self):
        r = self._session.get(f"{self.ha_url}/states/sensor.soil_moisture")
        if r.status_code == requests.codes.ok:
            self.data.soil_moisture = float(r.json()['state'])
        else:
            logger.warning("Couldn't get soil moisture -- %d", r.status_code)

    def _get_electric_cost(self):
        r = self._session.get(
            f"{self.ha_url}/states/sensor.comed_5_minute_price")
        if r.status_code == requests.codes.ok:
            self.data.electric_cost = float(r.json()['state'])
        else:
            logger.warning("Couldn't get electric price -- %d", r.status_code)

    def _get_forecast(self, ws: websockets.WebSocketClientProtocol):
        msg = self._call_service(ws, "weather", "get_forecasts", "weather.kpwk_daynight", True, {
            "type": "hourly"
        })

        if "result" not in msg:
            logger.warning("Didn't get result from weather")
            return
        self.data.forecast = msg['result']['response']['weather.kpwk_daynight']['forecast']

    def _get_daily_low_high(self, ws):
        msg = self._call_service(ws, "weather", "get_forecasts", "weather.kpwk_daynight", True, {
            "type": "twice_daily"
        })

        if "result" not in msg:
            logger.warning("Didn't get result from weather")
            return

        try:
            data = msg['result']['response']['weather.kpwk_daynight']['forecast']
            today = datetime.datetime.today()
            for point in (0, 1):
                if datetime.datetime.fromisoformat(data[point]['datetime']).date() == datetime.datetime.today().date():
                    if data[point]['is_daytime']:
                        self.data.day_lowhigh[1] = data[point]['temperature']
                        self.data.day_lowhigh_date = today
                    else:
                        self.data.day_lowhigh[0] = data[point]['temperature']
                        self.data.day_lowhigh_date = today
        except IndexError:
            logger.exception("Couldn't get daynight info")
        except KeyError:
            logger.exception("Couldn't get daynight info")

    def _get_daily_energy_usage(self):
        # TODO: Switch to websocket API to use statistics_during_period?
        today = datetime.date.today()
        r = self._session.get(f"{self.ha_url}/history/period/{today.isoformat()}T00:00:00-06:00", params={  # TODO: Timezone
            "filter_entity_id": "sensor.home_energy_meter_gen5_electric_consumption_kwh",
            "minimal_response": ""
        })
        if r.status_code == requests.codes.ok:
            data = r.json()[0]
            energy_sum = 0
            for previous, current in zip(data, data[1:]):
                try:
                    if float(current['state']) > float(previous['state']):
                        energy_sum += float(current['state']) - \
                            float(previous['state'])
                    else:
                        # Assumes there was a reset to zero
                        energy_sum += float(current['state'])
                except ValueError:
                    logger.warning(
                        "ValueError when calculating energy, skipping point -- %s, %s", current['state'], previous['state'])
            self.data.daily_energy = energy_sum
        else:
            logger.warning("Couldn't get energy usage -- %d", r.status_code)
