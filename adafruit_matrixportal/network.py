# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams, written for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense
"""
`adafruit_matrixportal.network`
================================================================================

Helper library for the Adafruit RGB Matrix Shield + Metro M4 Airlift Lite.

* Author(s): Melissa LeBlanc-Williams

Implementation Notes
--------------------

**Hardware:**

* `Adafruit Metro M4 Express AirLift <https://www.adafruit.com/product/4000>`_
* `Adafruit RGB Matrix Shield <https://www.adafruit.com/product/2601>`_
* `64x32 RGB LED Matrix <https://www.adafruit.com/product/2278>`_

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases

"""

import os
import time
import gc
from micropython import const
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
from adafruit_io.adafruit_io import IO_HTTP, AdafruitIO_RequestError
import adafruit_requests as requests
import supervisor
import rtc
from adafruit_matrixportal.wifi import WiFi
from adafruit_matrixportal.fakerequests import Fake_Requests

try:
    from secrets import secrets
except ImportError:
    print(
        """WiFi settings are kept in secrets.py, please add them there!
the secrets dictionary must contain 'ssid' and 'password' at a minimum"""
    )
    raise

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_MatrixPortal.git"

# pylint: disable=line-too-long
# pylint: disable=too-many-lines
# you'll need to pass in an io username and key
TIME_SERVICE = (
    "https://io.adafruit.com/api/v2/%s/integrations/time/strftime?x-aio-key=%s"
)
# our strftime is %Y-%m-%d %H:%M:%S.%L %j %u %z %Z see http://strftime.net/ for decoding details
# See https://apidock.com/ruby/DateTime/strftime for full options
TIME_SERVICE_STRFTIME = (
    "&fmt=%25Y-%25m-%25d+%25H%3A%25M%3A%25S.%25L+%25j+%25u+%25z+%25Z"
)
LOCALFILE = "local.txt"
# pylint: enable=line-too-long

STATUS_NO_CONNECTION = (100, 0, 0)
STATUS_CONNECTING = (0, 0, 100)
STATUS_FETCHING = (200, 100, 0)
STATUS_DOWNLOADING = (0, 100, 100)
STATUS_CONNECTED = (0, 100, 0)
STATUS_DATA_RECEIVED = (0, 0, 100)
STATUS_OFF = (0, 0, 0)

CONTENT_TEXT = const(1)
CONTENT_JSON = const(2)
CONTENT_IMAGE = const(3)


class HttpError(Exception):
    """HTTP Specific Error"""


class Network:
    """Class representing the Adafruit RGB Matrix Portal.

    :param status_neopixel: The pin for the status NeoPixel. Use ``board.NEOPIXEL`` for the on-board
                            NeoPixel. Defaults to ``None``, not the status LED
    :param esp: A passed ESP32 object, Can be used in cases where the ESP32 chip needs to be used
                             before calling the pyportal class. Defaults to ``None``.
    :param busio.SPI external_spi: A previously declared spi object. Defaults to ``None``.
    :param bool extract_values: If true, single-length fetched values are automatically extracted
                                from lists and tuples. Defaults to ``True``.
    :param debug: Turn on debug print outs. Defaults to False.

    """

    # pylint: disable=too-many-instance-attributes, too-many-locals, too-many-branches, too-many-statements
    def __init__(
        self,
        *,
        status_neopixel=None,
        esp=None,
        external_spi=None,
        extract_values=True,
        debug=False,
    ):
        self._wifi = WiFi(
            status_neopixel=status_neopixel, esp=esp, external_spi=external_spi
        )
        self._debug = debug
        self.json_transform = []
        self._extract_values = extract_values

        try:
            os.stat(LOCALFILE)
            self.uselocal = True
        except OSError:
            self.uselocal = False

        requests.set_socket(socket, self._wifi.esp)

        gc.collect()

    def neo_status(self, value):
        """The status NeoPixel.

        :param value: The color to change the NeoPixel.

        """
        self._wifi.neo_status(value)

    @staticmethod
    def json_traverse(json, path):
        """
        Traverse down the specified JSON path and return the value or values

        :param json: JSON data to traverse
        :param list path: The path that we want to follow

        """
        value = json
        if not isinstance(path, (list, tuple)):
            raise ValueError(
                "The json_path parameter should be enclosed in a list or tuple."
            )
        for x in path:
            value = value[x]
            gc.collect()
        return value

    def add_json_transform(self, json_transform):
        """Add a function that is applied to JSON data when data is fetched

        :param json_transform: A function or a list of functions to call with the parsed JSON.
                               Changes and additions are permitted for the ``dict`` object.
        """
        if callable(json_transform):
            self.json_transform.append(json_transform)
        else:
            self.json_transform.extend(filter(callable, json_transform))

    def get_local_time(self, location=None):
        # pylint: disable=line-too-long
        """Fetch and "set" the local time of this microcontroller to the local time at the location, using an internet time API.

        :param str location: Your city and country, e.g. ``"New York, US"``.

        """
        # pylint: enable=line-too-long
        self.connect()
        api_url = None
        try:
            aio_username = secrets["aio_username"]
            aio_key = secrets["aio_key"]
        except KeyError:
            raise KeyError(
                "\n\nOur time service requires a login/password to rate-limit. Please register for a free adafruit.io account and place the user/key in your secrets file under 'aio_username' and 'aio_key'"  # pylint: disable=line-too-long
            ) from KeyError

        if location is None:
            location = secrets.get("timezone")
        if location:
            print("Getting time for timezone", location)
            api_url = (TIME_SERVICE + "&tz=%s") % (aio_username, aio_key, location)
        else:  # we'll try to figure it out from the IP address
            print("Getting time from IP address")
            api_url = TIME_SERVICE % (aio_username, aio_key)
        api_url += TIME_SERVICE_STRFTIME
        try:
            response = requests.get(api_url, timeout=10)
            if response.status_code != 200:
                error_message = (
                    "Error connection to Adafruit IO. The response was: "
                    + response.text
                )
                raise ValueError(error_message)
            if self._debug:
                print("Time request: ", api_url)
                print("Time reply: ", response.text)
            times = response.text.split(" ")
            the_date = times[0]
            the_time = times[1]
            year_day = int(times[2])
            week_day = int(times[3])
            is_dst = None  # no way to know yet
        except KeyError:
            raise KeyError(
                "Was unable to lookup the time, try setting secrets['timezone'] according to http://worldtimeapi.org/timezones"  # pylint: disable=line-too-long
            ) from KeyError
        year, month, mday = [int(x) for x in the_date.split("-")]
        the_time = the_time.split(".")[0]
        hours, minutes, seconds = [int(x) for x in the_time.split(":")]
        now = time.struct_time(
            (year, month, mday, hours, minutes, seconds, week_day, year_day, is_dst)
        )
        rtc.RTC().datetime = now

        # now clean up
        response.close()
        response = None
        gc.collect()

    def wget(self, url, filename, *, chunk_size=12000):
        """Download a url and save to filename location, like the command wget.

        :param url: The URL from which to obtain the data.
        :param filename: The name of the file to save the data to.
        :param chunk_size: how much data to read/write at a time.

        """
        print("Fetching stream from", url)

        self.neo_status(STATUS_FETCHING)
        response = requests.get(url, stream=True)

        headers = {}
        for title, content in response.headers.items():
            headers[title.lower()] = content

        if response.status_code == 200:
            print("Reply is OK!")
            self.neo_status((0, 0, 100))  # green = got data
        else:
            if self._debug:
                if "content-length" in headers:
                    print("Content-Length: {}".format(int(headers["content-length"])))
                if "date" in headers:
                    print("Date: {}".format(headers["date"]))
            self.neo_status((100, 0, 0))  # red = http error
            raise HttpError(
                "Code {}: {}".format(
                    response.status_code, response.reason.decode("utf-8")
                )
            )

        if self._debug:
            print(response.headers)
        if "content-length" in headers:
            content_length = int(headers["content-length"])
        else:
            raise RuntimeError("Content-Length missing from headers")
        remaining = content_length
        print("Saving data to ", filename)
        stamp = time.monotonic()
        file = open(filename, "wb")
        for i in response.iter_content(min(remaining, chunk_size)):  # huge chunks!
            self.neo_status(STATUS_DOWNLOADING)
            remaining -= len(i)
            file.write(i)
            if self._debug:
                print(
                    "Read %d bytes, %d remaining"
                    % (content_length - remaining, remaining)
                )
            else:
                print(".", end="")
            if not remaining:
                break
            self.neo_status(STATUS_FETCHING)
        file.close()

        response.close()
        stamp = time.monotonic() - stamp
        print(
            "Created file of %d bytes in %0.1f seconds" % (os.stat(filename)[6], stamp)
        )
        self.neo_status(STATUS_OFF)
        if not content_length == os.stat(filename)[6]:
            raise RuntimeError

    def connect(self):
        """
        Connect to WiFi using the settings found in secrets.py
        """
        self._wifi.neo_status(STATUS_CONNECTING)
        while not self._wifi.esp.is_connected:
            # secrets dictionary must contain 'ssid' and 'password' at a minimum
            print("Connecting to AP", secrets["ssid"])
            if secrets["ssid"] == "CHANGE ME" or secrets["password"] == "CHANGE ME":
                change_me = "\n" + "*" * 45
                change_me += "\nPlease update the 'secrets.py' file on your\n"
                change_me += "CIRCUITPY drive to include your local WiFi\n"
                change_me += "access point SSID name in 'ssid' and SSID\n"
                change_me += "password in 'password'. Then save to reload!\n"
                change_me += "*" * 45
                raise OSError(change_me)
            self._wifi.neo_status(STATUS_NO_CONNECTION)  # red = not connected
            try:
                self._wifi.esp.connect(secrets)
            except RuntimeError as error:
                print("Could not connect to internet", error)
                print("Retrying in 3 seconds...")
                time.sleep(3)

    def _get_io_client(self):
        self.connect()

        try:
            aio_username = secrets["aio_username"]
            aio_key = secrets["aio_key"]
        except KeyError:
            raise KeyError(
                "Adafruit IO secrets are kept in secrets.py, please add them there!\n\n"
            ) from KeyError

        return IO_HTTP(aio_username, aio_key, requests)

    def push_to_io(self, feed_key, data):
        """Push data to an adafruit.io feed

        :param str feed_key: Name of feed key to push data to.
        :param data: data to send to feed

        """

        io_client = self._get_io_client()

        while True:
            try:
                feed_id = io_client.get_feed(feed_key)
            except AdafruitIO_RequestError:
                # If no feed exists, create one
                feed_id = io_client.create_new_feed(feed_key)
            except RuntimeError as exception:
                print("An error occured, retrying! 1 -", exception)
                continue
            break

        while True:
            try:
                io_client.send_data(feed_id["key"], data)
            except RuntimeError as exception:
                print("An error occured, retrying! 2 -", exception)
                continue
            except NameError as exception:
                print(feed_id["key"], data, exception)
                continue
            break

    def get_io_feed(self, feed_key, detailed=False):
        """Return the Adafruit IO Feed that matches the feed key

        :param str feed_key: Name of feed key to match.
        :param bool detailed: Whether to return additional detailed information

        """
        io_client = self._get_io_client()

        while True:
            try:
                return io_client.get_feed(feed_key, detailed=detailed)
            except RuntimeError as exception:
                print("An error occured, retrying! 1 -", exception)
                continue
            break

    def get_io_group(self, group_key):
        """Return the Adafruit IO Group that matches the group key

        :param str group_key: Name of group key to match.

        """
        io_client = self._get_io_client()

        while True:
            try:
                return io_client.get_group(group_key)
            except RuntimeError as exception:
                print("An error occured, retrying! 1 -", exception)
                continue
            break

    def get_io_data(self, feed_key):
        """Return all values from Adafruit IO Feed Data that matches the feed key

        :param str feed_key: Name of feed key to receive data from.

        """
        io_client = self._get_io_client()

        while True:
            try:
                return io_client.receive_all_data(feed_key)
            except RuntimeError as exception:
                print("An error occured, retrying! 1 -", exception)
                continue
            break

    def fetch(self, url, *, headers=None, timeout=10):
        """Fetch data from the specified url and return a response object"""
        gc.collect()
        if self._debug:
            print("Free mem: ", gc.mem_free())  # pylint: disable=no-member

        response = None
        if self.uselocal:
            print("*** USING LOCALFILE FOR DATA - NOT INTERNET!!! ***")
            response = Fake_Requests(LOCALFILE)

        if not response:
            self.connect()
            # great, lets get the data
            print("Retrieving data...", end="")
            self.neo_status(STATUS_FETCHING)  # yellow = fetching data
            gc.collect()
            response = requests.get(url, headers=headers, timeout=timeout)
            gc.collect()

        return response

    def fetch_data(
        self, url, *, headers=None, json_path=None, regexp_path=None, timeout=10,
    ):
        """Fetch data from the specified url and perfom any parsing"""
        json_out = None
        values = []
        content_type = CONTENT_TEXT

        response = self.fetch(url, headers=headers, timeout=timeout)

        headers = {}
        for title, content in response.headers.items():
            headers[title.lower()] = content
        gc.collect()
        if self._debug:
            print("Headers:", headers)
        if response.status_code == 200:
            print("Reply is OK!")
            self.neo_status(STATUS_DATA_RECEIVED)  # green = got data
            if "content-type" in headers:
                if "image/" in headers["content-type"]:
                    content_type = CONTENT_IMAGE
                elif "application/json" in headers["content-type"]:
                    content_type = CONTENT_JSON
                elif "application/javascript" in headers["content-type"]:
                    content_type = CONTENT_JSON
        else:
            if self._debug:
                if "content-length" in headers:
                    print("Content-Length: {}".format(int(headers["content-length"])))
                if "date" in headers:
                    print("Date: {}".format(headers["date"]))
            self.neo_status((100, 0, 0))  # red = http error
            raise HttpError(
                "Code {}: {}".format(
                    response.status_code, response.reason.decode("utf-8")
                )
            )

        if content_type == CONTENT_JSON and json_path is not None:
            if isinstance(json_path, (list, tuple)) and (
                not json_path or not isinstance(json_path[0], (list, tuple))
            ):
                json_path = (json_path,)
            try:
                gc.collect()
                json_out = response.json()
                if self._debug:
                    print(json_out)
                gc.collect()
            except ValueError:  # failed to parse?
                print("Couldn't parse json: ", response.text)
                raise
            except MemoryError:
                supervisor.reload()

        if regexp_path:
            import re  # pylint: disable=import-outside-toplevel

        # optional JSON post processing, apply any transformations
        # these MAY change/add element
        for idx, json_transform in enumerate(self.json_transform):
            try:
                json_transform(json_out)
            except Exception as error:
                print("Exception from json_transform: ", idx, error)
                raise

        # extract desired text/values from json
        if json_out and json_path:
            for path in json_path:
                try:
                    values.append(self.json_traverse(json_out, path))
                except KeyError:
                    print(json_out)
                    raise
        elif content_type == CONTENT_TEXT and regexp_path:
            for regexp in regexp_path:
                values.append(re.search(regexp, response.text).group(1))
        else:
            if json_out:
                # No path given, so return JSON as string for compatibility
                import json  # pylint: disable=import-outside-toplevel

                values = json.dumps(response.json())
            else:
                values = response.text

        # we're done with the requests object, lets delete it so we can do more!
        json_out = None
        response = None
        gc.collect()
        if self._extract_values and len(values) == 1:
            return values[0]

        return values

    @property
    def ip_address(self):
        """Return the IP Address nicely formatted"""
        return self._wifi.esp.pretty_ip(self._wifi.esp.ip_address)
