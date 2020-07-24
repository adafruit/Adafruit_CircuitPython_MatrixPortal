# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams, written for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense
"""
`adafruit_matrixportal`
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

* Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice
"""

import os
import time
import gc
import board
import busio
from digitalio import DigitalInOut
import neopixel
import terminalio
from adafruit_esp32spi import adafruit_esp32spi, adafruit_esp32spi_wifimanager
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
from adafruit_bitmap_font import bitmap_font
import displayio
from adafruit_display_text.label import Label
from adafruit_io.adafruit_io import IO_HTTP, AdafruitIO_RequestError
import adafruit_requests as requests
import supervisor
import rtc
import rgbmatrix
import framebufferio

try:
    from secrets import secrets
except ImportError:
    print(
        """WiFi settings are kept in secrets.py, please add them there!
the secrets dictionary must contain 'ssid' and 'password' at a minimum"""
    )
    raise

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_PyPortal.git"

# pylint: disable=line-too-long
# pylint: disable=too-many-lines
# you'll need to pass in an io username, width, height, format (bit depth), io key, and then url!
IMAGE_CONVERTER_SERVICE = "https://io.adafruit.com/api/v2/%s/integrations/image-formatter?x-aio-key=%s&width=%d&height=%d&output=BMP%d&url=%s"
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


class Fake_Requests:
    """For faking 'requests' using a local file instead of the network."""

    def __init__(self, filename):
        self._filename = filename
        with open(filename, "r") as file:
            self.text = file.read()

    def json(self):
        """json parsed version for local requests."""
        import json  # pylint: disable=import-outside-toplevel

        return json.loads(self.text)


class MatrixPortal:
    """Class representing the Adafruit RGB Matrix Portal.

    :param url: The URL of your data source. Defaults to ``None``.
    :param headers: The headers for authentication, typically used by Azure API's.
    :param json_path: The list of json traversal to get data out of. Can be list of lists for
                      multiple data points. Defaults to ``None`` to not use json.
    :param regexp_path: The list of regexp strings to get data out (use a single regexp group). Can
                        be list of regexps for multiple data points. Defaults to ``None`` to not
                        use regexp.
    :param default_bg: The path to your default background image file or a hex color.
                       Defaults to 0x000000.
    :param status_neopixel: The pin for the status NeoPixel. Use ``board.NEOPIXEL`` for the on-board
                            NeoPixel. Defaults to ``None``, not the status LED
    :param json_transform: A function or a list of functions to call with the parsed JSON.
                           Changes and additions are permitted for the ``dict`` object.
    :param esp: A passed ESP32 object, Can be used in cases where the ESP32 chip needs to be used
                             before calling the pyportal class. Defaults to ``None``.
    :param busio.SPI external_spi: A previously declared spi object. Defaults to ``None``.
    :param debug: Turn on debug print outs. Defaults to False.

    """

    # pylint: disable=too-many-instance-attributes, too-many-locals, too-many-branches, too-many-statements
    def __init__(
        self,
        *,
        url=None,
        headers=None,
        json_path=None,
        regexp_path=None,
        default_bg=0x000000,
        status_neopixel=None,
        json_transform=None,
        esp=None,
        external_spi=None,
        debug=False
    ):

        self._debug = debug

        try:
            displayio.release_displays()
            matrix = rgbmatrix.RGBMatrix(
                width=64,
                height=32,
                bit_depth=2,
                rgb_pins=[board.D2, board.D3, board.D4, board.D5, board.D6, board.D7],
                addr_pins=[board.A0, board.A1, board.A2, board.A3],
                clock_pin=board.A4,
                latch_pin=board.D10,
                output_enable_pin=board.D9,
            )
            self.display = framebufferio.FramebufferDisplay(matrix)
        except ValueError:
            raise RuntimeError("Failed to initialize RGB Matrix")

        self._url = url
        self._headers = headers
        if json_path:
            if isinstance(json_path[0], (list, tuple)):
                self._json_path = json_path
            else:
                self._json_path = (json_path,)
        else:
            self._json_path = None

        self._regexp_path = regexp_path

        if status_neopixel:
            self.neopix = neopixel.NeoPixel(status_neopixel, 1, brightness=0.2)
        else:
            self.neopix = None
        self.neo_status(0)

        try:
            os.stat(LOCALFILE)
            self._uselocal = True
        except OSError:
            self._uselocal = False

        if self._debug:
            print("Init display")
        self.splash = displayio.Group(max_size=15)

        if self._debug:
            print("Init background")
        self._bg_group = displayio.Group(max_size=1)
        self._bg_file = None
        self._default_bg = default_bg
        self.splash.append(self._bg_group)

        if esp:  # If there was a passed ESP Object
            if self._debug:
                print("Passed ESP32 to MatrixPortal")
            self._esp = esp
            if external_spi:  # If SPI Object Passed
                spi = external_spi
            else:  # Else: Make ESP32 connection
                spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
        else:
            if self._debug:
                print("Init ESP32")
            esp32_ready = DigitalInOut(board.ESP_BUSY)
            esp32_gpio0 = DigitalInOut(board.ESP_GPIO0)
            esp32_reset = DigitalInOut(board.ESP_RESET)
            esp32_cs = DigitalInOut(board.ESP_CS)
            spi = busio.SPI(board.SCK, board.MOSI, board.MISO)

            self._esp = adafruit_esp32spi.ESP_SPIcontrol(
                spi, esp32_cs, esp32_ready, esp32_reset, esp32_gpio0
            )
        # self._esp._debug = 1
        for _ in range(3):  # retries
            try:
                print("ESP firmware:", self._esp.firmware_version)
                break
            except RuntimeError:
                print("Retrying ESP32 connection")
                time.sleep(1)
                self._esp.reset()
        else:
            raise RuntimeError("Was not able to find ESP32")
        requests.set_socket(socket, self._esp)

        if url and not self._uselocal:
            self._connect_esp()

        if self._debug:
            print("My IP address is", self._esp.pretty_ip(self._esp.ip_address))

        # set the default background
        self.set_background(self._default_bg)
        self.display.show(self.splash)

        # Add any JSON translators
        self._json_transform = []
        if json_transform:
            if callable(json_transform):
                self._json_transform.append(json_transform)
            else:
                self._json_transform.extend(filter(callable, json_transform))

        self._image_json_path = None
        self._image_url_path = None
        self._image_resize = None
        self._image_position = None
        self._image_dim_json_path = None
        self._text = []
        self._text_color = []
        self._text_position = []
        self._text_wrap = []
        self._text_maxlen = []
        self._text_transform = []
        self._text_scrolling = []
        self._scrolling_index = None
        self._text_font = terminalio.FONT

        gc.collect()

    # pylint: disable=too-many-arguments
    def set_image_settings(
        self,
        image_json_path=None,
        image_resize=None,
        image_position=None,
        image_dim_json_path=None,
        image_url_path=None,
    ):
        """
        Setup image settings for retrieving and setting a background image

        :param image_json_path: The JSON traversal path for a background image to display. Defaults
                                to ``None``.
        :param image_resize: What size to resize the image we got from the json_path, make this a
                             tuple of the width and height you want. Defaults to ``None``.
        :param image_position: The position of the image on the display as an (x, y) tuple. Defaults
                               to ``None``.
        :param image_dim_json_path: The JSON traversal path for the original dimensions of image
                                    tuple. Used with fetch(). Defaults to ``None``.
        :param image_url_path: The HTTP traversal path for a background image to display.
                                 Defaults to ``None``.

        """
        self._image_json_path = image_json_path
        self._image_url_path = image_url_path
        self._image_resize = image_resize
        self._image_position = image_position
        self._image_dim_json_path = image_dim_json_path
        if image_json_path or image_url_path:
            if self._debug:
                print("Init image path")
            if not self._image_position:
                self._image_position = (0, 0)  # default to top corner
            if not self._image_resize:
                self._image_resize = (
                    self.display.width,
                    self.display.height,
                )  # default to full screen

    def add_text(
        self,
        text_position=None,
        text_font=None,
        text_color=0x808080,
        text_wrap=False,
        text_maxlen=0,
        text_transform=None,
        scrolling=False,
    ):
        """
        Add text labels with settings

        :param str text_font: The path to your font file for your data text display.
        :param text_position: The position of your extracted text on the display in an (x, y) tuple.
                              Can be a list of tuples for when there's a list of json_paths, for
                              example.
        :param text_color: The color of the text, in 0xRRGGBB format. Can be a list of colors for
                           when there's multiple texts. Defaults to ``None``.
        :param text_wrap: Whether or not to wrap text (for long text data chunks). Defaults to
                          ``False``, no wrapping.
        :param text_maxlen: The max length of the text for text wrapping. Defaults to 0.
        :param text_transform: A function that will be called on the text before display
        :param bool scrolling: If true, text is placed offscreen and the scroll() function is used
                               to scroll text on a pixel-by-pixel basis. Multiple text labels with
                               the scrolling set to True will be cycled through.

        """
        if text_font:
            if text_font is terminalio.FONT:
                self._text_font = text_font
            else:
                self._text_font = bitmap_font.load_font(text_font)
        if not text_wrap:
            text_wrap = 0
        if not text_maxlen:
            text_maxlen = 0
        if not text_transform:
            text_transform = None
        if scrolling:
            text_position = (self.display.width, text_position[1])

        gc.collect()

        if self._debug:
            print("Init text area")
        self._text.append(None)
        self._text_color.append(text_color)
        self._text_position.append(text_position)
        self._text_wrap.append(text_wrap)
        self._text_maxlen.append(text_maxlen)
        self._text_transform.append(text_transform)
        self._text_scrolling.append(scrolling)

    # pylint: enable=too-many-arguments

    def set_headers(self, headers):
        """Set the headers used by fetch().

        :param headers: The new header dictionary

        """
        self._headers = headers

    def set_background(self, file_or_color, position=None):
        """The background image to a bitmap file.

        :param file_or_color: The filename of the chosen background image, or a hex color.

        """
        print("Set background to ", file_or_color)
        while self._bg_group:
            self._bg_group.pop()

        if not position:
            position = (0, 0)  # default in top corner

        if not file_or_color:
            return  # we're done, no background desired
        if self._bg_file:
            self._bg_file.close()
        if isinstance(file_or_color, str):  # its a filenme:
            self._bg_file = open(file_or_color, "rb")
            background = displayio.OnDiskBitmap(self._bg_file)
            self._bg_sprite = displayio.TileGrid(
                background,
                pixel_shader=displayio.ColorConverter(),
                x=position[0],
                y=position[1],
            )
        elif isinstance(file_or_color, int):
            # Make a background color fill
            color_bitmap = displayio.Bitmap(self.display.width, self.display.height, 1)
            color_palette = displayio.Palette(1)
            color_palette[0] = file_or_color
            self._bg_sprite = displayio.TileGrid(
                color_bitmap, pixel_shader=color_palette, x=position[0], y=position[1],
            )
        else:
            raise RuntimeError("Unknown type of background")
        self._bg_group.append(self._bg_sprite)
        try:
            self.display.refresh()
            gc.collect()
        except AttributeError:
            self.display.refresh_soon()
            gc.collect()
            self.display.wait_for_frame()

    def preload_font(self, glyphs=None):
        # pylint: disable=line-too-long
        """Preload font.

        :param glyphs: The font glyphs to load. Defaults to ``None``, uses alphanumeric glyphs if
                       None.
        """
        # pylint: enable=line-too-long
        if not glyphs:
            glyphs = b"0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-!,. \"'?!"
        print("Preloading font glyphs:", glyphs)
        if self._text_font and self._text_font is not terminalio.FONT:
            self._text_font.load_glyphs(glyphs)

    def set_text(self, val, index=0):
        """Display text, with indexing into our list of text boxes.

        :param str val: The text to be displayed
        :param index: Defaults to 0.

        """
        # Make sure at least a single label exists
        if not self._text:
            self.add_text()
        if self._text_font:
            string = str(val)
            if self._text_maxlen[index]:
                string = string[: self._text_maxlen[index]]
            if self._text[index]:
                # print("Replacing text area with :", string)
                # self._text[index].text = string
                # return
                try:
                    text_index = self.splash.index(self._text[index])
                except AttributeError:
                    for i in range(len(self.splash)):
                        if self.splash[i] == self._text[index]:
                            text_index = i
                            break

                self._text[index] = Label(self._text_font, text=string)
                self._text[index].color = self._text_color[index]
                self._text[index].x = self._text_position[index][0]
                self._text[index].y = self._text_position[index][1]
                self.splash[text_index] = self._text[index]
                return

            if self._text_position[index]:  # if we want it placed somewhere...
                print("Making text area with string:", string)
                self._text[index] = Label(self._text_font, text=string)
                self._text[index].color = self._text_color[index]
                self._text[index].x = self._text_position[index][0]
                self._text[index].y = self._text_position[index][1]
                self.splash.append(self._text[index])

    def neo_status(self, value):
        """The status NeoPixel.

        :param value: The color to change the NeoPixel.

        """
        if self.neopix:
            self.neopix.fill(value)

    @staticmethod
    def _json_traverse(json, path):
        value = json
        for x in path:
            value = value[x]
            gc.collect()
        return value

    def get_local_time(self, location=None):
        # pylint: disable=line-too-long
        """Fetch and "set" the local time of this microcontroller to the local time at the location, using an internet time API.

        :param str location: Your city and country, e.g. ``"New York, US"``.

        """
        # pylint: enable=line-too-long
        self._connect_esp()
        api_url = None
        try:
            aio_username = secrets["aio_username"]
            aio_key = secrets["aio_key"]
        except KeyError:
            raise KeyError(
                "\n\nOur time service requires a login/password to rate-limit. Please register for a free adafruit.io account and place the user/key in your secrets file under 'aio_username' and 'aio_key'"  # pylint: disable=line-too-long
            )

        location = secrets.get("timezone", location)
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
                raise ValueError(response.text)
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
            )
        year, month, mday = [int(x) for x in the_date.split("-")]
        the_time = the_time.split(".")[0]
        hours, minutes, seconds = [int(x) for x in the_time.split(":")]
        now = time.struct_time(
            (year, month, mday, hours, minutes, seconds, week_day, year_day, is_dst)
        )
        print(now)
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

        self.neo_status((200, 100, 0))
        r = requests.get(url, stream=True)

        if self._debug:
            print(r.headers)
        content_length = int(r.headers["content-length"])
        remaining = content_length
        print("Saving data to ", filename)
        stamp = time.monotonic()
        file = open(filename, "wb")
        for i in r.iter_content(min(remaining, chunk_size)):  # huge chunks!
            self.neo_status((0, 100, 100))
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
            self.neo_status((200, 100, 0))
        file.close()

        r.close()
        stamp = time.monotonic() - stamp
        print(
            "Created file of %d bytes in %0.1f seconds" % (os.stat(filename)[6], stamp)
        )
        self.neo_status((0, 0, 0))
        if not content_length == os.stat(filename)[6]:
            raise RuntimeError

    def _connect_esp(self):
        self.neo_status((0, 0, 100))
        while not self._esp.is_connected:
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
            self.neo_status((100, 0, 0))  # red = not connected
            try:
                self._esp.connect(secrets)
            except RuntimeError as error:
                print("Could not connect to internet", error)
                print("Retrying in 3 seconds...")
                time.sleep(3)

    @staticmethod
    def image_converter_url(image_url, width, height, color_depth=16):
        """Generate a converted image url from the url passed in,
           with the given width and height. aio_username and aio_key must be
           set in secrets."""
        try:
            aio_username = secrets["aio_username"]
            aio_key = secrets["aio_key"]
        except KeyError:
            raise KeyError(
                "\n\nOur image converter service require a login/password to rate-limit. Please register for a free adafruit.io account and place the user/key in your secrets file under 'aio_username' and 'aio_key'"  # pylint: disable=line-too-long
            )

        return IMAGE_CONVERTER_SERVICE % (
            aio_username,
            aio_key,
            width,
            height,
            color_depth,
            image_url,
        )

    def push_to_io(self, feed_key, data):
        # pylint: disable=line-too-long
        """Push data to an adafruit.io feed

        :param str feed_key: Name of feed key to push data to.
        :param data: data to send to feed

        """
        # pylint: enable=line-too-long

        try:
            aio_username = secrets["aio_username"]
            aio_key = secrets["aio_key"]
        except KeyError:
            raise KeyError(
                "Adafruit IO secrets are kept in secrets.py, please add them there!\n\n"
            )

        wifi = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(
            self._esp, secrets, None
        )
        io_client = IO_HTTP(aio_username, aio_key, wifi)

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

    def _get_next_scrollable_text_index(self):
        index = self._scrolling_index
        while True:
            if index is None:
                index = 0
            else:
                index += 1
            if index >= len(self._text_scrolling):
                index = 0
            if self._text_scrolling[index]:
                return index
            if index == self._scrolling_index:
                return None

    def scroll(self):
        """Scroll any text that needs scrolling. We also want to queue up
        multiple lines one after another. To get simultaneous lines, we can
        simply use a line break."""

        if self._scrolling_index is None:  # Not initialized yet
            next_index = self._get_next_scrollable_text_index()
            if next_index is None:
                return
            self._scrolling_index = next_index

        # set line to label with self._scrolling_index

        self._text[self._scrolling_index].x = self._text[self._scrolling_index].x - 1
        line_width = self._text[self._scrolling_index].bounding_box[2]
        if self._text[self._scrolling_index].x < -line_width:
            # Find the next line
            self._scrolling_index = self._get_next_scrollable_text_index()
            self._text[self._scrolling_index].x = self.display.width

    def fetch(self, refresh_url=None, timeout=10):
        """Fetch data from the url we initialized with, perfom any parsing,
        and display text or graphics. This function does pretty much everything
        Optionally update the URL
        """
        if refresh_url:
            self._url = refresh_url
        json_out = None
        image_url = None
        values = []

        gc.collect()
        if self._debug:
            print("Free mem: ", gc.mem_free())  # pylint: disable=no-member

        r = None
        if self._uselocal:
            print("*** USING LOCALFILE FOR DATA - NOT INTERNET!!! ***")
            r = Fake_Requests(LOCALFILE)

        if not r:
            self._connect_esp()
            # great, lets get the data
            print("Retrieving data...", end="")
            self.neo_status((200, 100, 0))  # yellow = fetching data
            gc.collect()
            r = requests.get(self._url, headers=self._headers, timeout=timeout)
            gc.collect()
            self.neo_status((0, 0, 100))  # green = got data
            print("Reply is OK!")

        if self._debug:
            print(r.text)

        if self._image_json_path or self._json_path:
            try:
                gc.collect()
                json_out = r.json()
                gc.collect()
            except ValueError:  # failed to parse?
                print("Couldn't parse json: ", r.text)
                raise
            except MemoryError:
                supervisor.reload()

        if self._regexp_path:
            import re  # pylint: disable=import-outside-toplevel

        if self._image_url_path:
            image_url = self._image_url_path

        # optional JSON post processing, apply any transformations
        # these MAY change/add element
        for idx, json_transform in enumerate(self._json_transform):
            try:
                json_transform(json_out)
            except Exception as error:
                print("Exception from json_transform: ", idx, error)
                raise

        # extract desired text/values from json
        if self._json_path:
            for path in self._json_path:
                try:
                    values.append(MatrixPortal._json_traverse(json_out, path))
                except KeyError:
                    print(json_out)
                    raise
        elif self._regexp_path:
            for regexp in self._regexp_path:
                values.append(re.search(regexp, r.text).group(1))
        else:
            values = r.text

        if self._image_json_path:
            try:
                image_url = MatrixPortal._json_traverse(json_out, self._image_json_path)
            except KeyError as error:
                print("Error finding image data. '" + error.args[0] + "' not found.")
                self.set_background(self._default_bg)

        iwidth = 0
        iheight = 0
        if self._image_dim_json_path:
            iwidth = int(
                MatrixPortal._json_traverse(json_out, self._image_dim_json_path[0])
            )
            iheight = int(
                MatrixPortal._json_traverse(json_out, self._image_dim_json_path[1])
            )
            print("image dim:", iwidth, iheight)

        # we're done with the requests object, lets delete it so we can do more!
        json_out = None
        r = None
        gc.collect()

        if image_url:
            try:
                print("original URL:", image_url)
                if iwidth < iheight:
                    image_url = self.image_converter_url(
                        image_url,
                        int(
                            self._image_resize[1]
                            * self._image_resize[1]
                            / self._image_resize[0]
                        ),
                        self._image_resize[1],
                    )
                else:
                    image_url = self.image_converter_url(
                        image_url, self._image_resize[0], self._image_resize[1]
                    )
                print("convert URL:", image_url)
                # convert image to bitmap and cache
                # print("**not actually wgetting**")
                filename = "/cache.bmp"
                chunk_size = 4096  # default chunk size is 12K (for QSPI)
                try:
                    self.wget(image_url, filename, chunk_size=chunk_size)
                except OSError as error:
                    print(error)
                    raise OSError(
                        """\n\nNo writable filesystem found for saving datastream. Insert an SD card or set internal filesystem to be unsafe by setting 'disable_concurrent_write_protection' in the mount options in boot.py"""  # pylint: disable=line-too-long
                    )
                except RuntimeError as error:
                    print(error)
                    raise RuntimeError("wget didn't write a complete file")
                if iwidth < iheight:
                    pwidth = int(
                        self._image_resize[1]
                        * self._image_resize[1]
                        / self._image_resize[0]
                    )
                    self.set_background(
                        filename,
                        (
                            self._image_position[0]
                            + int((self._image_resize[0] - pwidth) / 2),
                            self._image_position[1],
                        ),
                    )
                else:
                    self.set_background(filename, self._image_position)

            except ValueError as error:
                print("Error displaying cached image. " + error.args[0])
                self.set_background(self._default_bg)
            finally:
                image_url = None
                gc.collect()

        # fill out all the text blocks
        if self._text:
            for i in range(len(self._text)):
                string = None
                if self._text_transform[i]:
                    func = self._text_transform[i]
                    string = func(values[i])
                else:
                    try:
                        string = "{:,d}".format(int(values[i]))
                    except (TypeError, ValueError):
                        string = values[i]  # ok its a string
                if self._debug:
                    print("Drawing text", string)
                if self._text_wrap[i]:
                    if self._debug:
                        print("Wrapping text")
                    lines = MatrixPortal.wrap_nicely(string, self._text_wrap[i])
                    string = "\n".join(lines)
                self.set_text(string, index=i)
        if len(values) == 1:
            return values[0]
        return values

    # return a list of lines with wordwrapping
    @staticmethod
    def wrap_nicely(string, max_chars):
        """A helper that will return a list of lines with word-break wrapping.

        :param str string: The text to be wrapped.
        :param int max_chars: The maximum number of characters on a line before wrapping.

        """
        string = string.replace("\n", "").replace("\r", "")  # strip confusing newlines
        words = string.split(" ")
        the_lines = []
        the_line = ""
        for w in words:
            if len(the_line + " " + w) <= max_chars:
                the_line += " " + w
            else:
                the_lines.append(the_line)
                the_line = "" + w
        if the_line:  # last line remaining
            the_lines.append(the_line)
        # remove first space from first line:
        the_lines[0] = the_lines[0][1:]
        return the_lines
