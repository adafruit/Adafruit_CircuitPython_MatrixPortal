# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams, written for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense
"""
`adafruit_matrixportal.matrixportal`
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

import gc
from time import sleep
import terminalio
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text.label import Label
from adafruit_matrixportal.network import Network
from adafruit_matrixportal.graphics import Graphics

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_MatrixPortal.git"


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
    :param int bit_depth: The number of bits per color channel. Defaults to 2.
    :param list alt_addr_pins: An alternate set of address pins to use. Defaults to None
    :param string color_order: A string containing the letter "R", "G", and "B" in the
                               order you want. Defaults to "RGB"
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
        bit_depth=2,
        alt_addr_pins=None,
        color_order="RGB",
        debug=False,
        width=64,
        height=32,
    ):

        self._debug = debug
        self.graphics = Graphics(
            default_bg=default_bg,
            bit_depth=bit_depth,
            width=width,
            height=height,
            alt_addr_pins=alt_addr_pins,
            color_order=color_order,
            debug=debug,
        )
        self.display = self.graphics.display

        self.network = Network(
            status_neopixel=status_neopixel,
            esp=esp,
            external_spi=external_spi,
            extract_values=False,
            debug=debug,
        )

        self._url = None
        self.url = url
        self._headers = headers
        self._json_path = None
        self.json_path = json_path

        self._regexp_path = regexp_path

        self.splash = self.graphics.splash

        # Add any JSON translators
        if json_transform:
            self.network.add_json_transform(json_transform)

        self._text = []
        self._text_color = []
        self._text_position = []
        self._text_wrap = []
        self._text_maxlen = []
        self._text_transform = []
        self._text_scrolling = []
        self._text_scale = []
        self._scrolling_index = None
        self._text_font = []
        self._text_line_spacing = []

        gc.collect()

    # pylint: disable=too-many-arguments
    def add_text(
        self,
        text_position=None,
        text_font=terminalio.FONT,
        text_color=0x808080,
        text_wrap=False,
        text_maxlen=0,
        text_transform=None,
        text_scale=1,
        scrolling=False,
        line_spacing=1.25,
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
        :param int text_scale: The factor to scale the default size of the text by
        :param bool scrolling: If true, text is placed offscreen and the scroll() function is used
                               to scroll text on a pixel-by-pixel basis. Multiple text labels with
                               the scrolling set to True will be cycled through.

        """
        if text_font is terminalio.FONT:
            self._text_font.append(text_font)
        else:
            self._text_font.append(bitmap_font.load_font(text_font))
        if not text_wrap:
            text_wrap = 0
        if not text_maxlen:
            text_maxlen = 0
        if not text_transform:
            text_transform = None
        if not isinstance(text_scale, (int, float)) or text_scale < 1:
            text_scale = 1
        text_scale = round(text_scale)
        if scrolling:
            if text_position is None:
                # Center text if position not specified
                text_position = (self.display.width, self.display.height // 2 - 1)
            else:
                text_position = (self.display.width, text_position[1])

        gc.collect()

        if self._debug:
            print("Init text area")
        self._text.append(None)
        self._text_color.append(self.html_color_convert(text_color))
        self._text_position.append(text_position)
        self._text_wrap.append(text_wrap)
        self._text_maxlen.append(text_maxlen)
        self._text_transform.append(text_transform)
        self._text_scale.append(text_scale)
        self._text_scrolling.append(scrolling)
        self._text_line_spacing.append(line_spacing)

        if scrolling and self._scrolling_index is None:  # Not initialized yet
            self._scrolling_index = self._get_next_scrollable_text_index()
        return len(self._text) - 1

    # pylint: enable=too-many-arguments

    @staticmethod
    def html_color_convert(color):
        """Convert an HTML color code to an integer

        :param color: The color value to be converted

        """
        if isinstance(color, str):
            if color[0] == "#":
                color = color.lstrip("#")
            return int(color, 16)
        return color  # Return unconverted

    def set_headers(self, headers):
        """Set the headers used by fetch().

        :param headers: The new header dictionary

        """
        self._headers = headers

    def set_background(self, file_or_color, position=None):
        """The background image to a bitmap file.

        :param file_or_color: The filename of the chosen background image, or a hex color.

        """
        self.graphics.set_background(file_or_color, position)

    def preload_font(self, glyphs=None, index=0):
        # pylint: disable=line-too-long
        """Preload font.

        :param glyphs: The font glyphs to load. Defaults to ``None``, uses alphanumeric glyphs if
                       None.
        """
        # pylint: enable=line-too-long
        if not glyphs:
            glyphs = b"0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-!,. \"'?!"
        print("Preloading font glyphs:", glyphs)
        if self._text_font[index] is not terminalio.FONT:
            self._text_font[index].load_glyphs(glyphs)

    def set_text_color(self, color, index=0):
        """Update the text color, with indexing into our list of text boxes.

        :param int color: The color value to be used
        :param index: Defaults to 0.

        """
        if 0 <= index < len(self._text_color):
            self._text_color[index] = self.html_color_convert(color)
            if self._text[index] is not None:
                self._text[index].color = self._text_color[index]
        else:
            raise IndexError(
                "index {} is out of bounds. Please call add_text() and set_text() first.".format(
                    index
                )
            )

    def set_text(self, val, index=0):
        """Display text, with indexing into our list of text boxes.

        :param str val: The text to be displayed
        :param index: Defaults to 0.

        """
        # Make sure at least a single label exists
        if not self._text:
            self.add_text()
        string = str(val)
        if self._text_maxlen[index]:
            string = string[: self._text_maxlen[index]]
        print("text index", self._text[index])
        index_in_splash = None

        if self._text[index] is not None:
            if self._debug:
                print("Replacing text area with :", string)
            index_in_splash = self.splash.index(self._text[index])
        elif self._debug:
            print("Creating text area with :", string)

        if len(string) > 0:
            self._text[index] = Label(
                self._text_font[index], text=string, scale=self._text_scale[index]
            )
            self._text[index].color = self._text_color[index]
            self._text[index].x = self._text_position[index][0]
            self._text[index].y = self._text_position[index][1]
            self._text[index].line_spacing = self._text_line_spacing[index]
        elif index_in_splash is not None:
            self._text[index] = None

        if index_in_splash is not None:
            if self._text[index] is not None:
                self.splash[index_in_splash] = self._text[index]
            else:
                del self.splash[index_in_splash]
        elif self._text[index] is not None:
            self.splash.append(self._text[index])

    def get_local_time(self, location=None):
        """Accessor function for get_local_time()"""
        return self.network.get_local_time(location=location)

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

    def push_to_io(self, feed_key, data):
        """Push data to an adafruit.io feed

        :param str feed_key: Name of feed key to push data to.
        :param data: data to send to feed

        """

        self.network.push_to_io(feed_key, data)

    def get_io_data(self, feed_key):
        """Return all values from the Adafruit IO Feed Data that matches the feed key

        :param str feed_key: Name of feed key to receive data from.

        """

        return self.network.get_io_data(feed_key)

    def get_io_feed(self, feed_key, detailed=False):
        """Return the Adafruit IO Feed that matches the feed key

        :param str feed_key: Name of feed key to match.
        :param bool detailed: Whether to return additional detailed information

        """
        return self.network.get_io_feed(feed_key, detailed)

    def get_io_group(self, group_key):
        """Return the Adafruit IO Group that matches the group key

        :param str group_key: Name of group key to match.

        """
        return self.network.get_io_group(group_key)

    def scroll(self):
        """Scroll any text that needs scrolling by a single frame. We also
        we want to queue up multiple lines one after another. To get
        simultaneous lines, we can simply use a line break.
        """

        if self._scrolling_index is None:  # Not initialized yet
            return

        self._text[self._scrolling_index].x = self._text[self._scrolling_index].x - 1
        line_width = (
            self._text[self._scrolling_index].bounding_box[2]
            * self._text_scale[self._scrolling_index]
        )
        if self._text[self._scrolling_index].x < -line_width:
            # Find the next line
            self._scrolling_index = self._get_next_scrollable_text_index()
            self._text[self._scrolling_index].x = self.graphics.display.width

    def scroll_text(self, frame_delay=0.02):
        """Scroll the entire text all the way across. We also
        we want to queue up multiple lines one after another. To get
        simultaneous lines, we can simply use a line break.
        """
        if self._scrolling_index is None:  # Not initialized yet
            return
        if self._text[self._scrolling_index] is not None:
            self._text[self._scrolling_index].x = self.graphics.display.width
            line_width = (
                self._text[self._scrolling_index].bounding_box[2]
                * self._text_scale[self._scrolling_index]
            )
            for _ in range(self.graphics.display.width + line_width + 1):
                self.scroll()
                sleep(frame_delay)
        else:
            raise RuntimeError(
                "Please assign text to the label with index {} before scrolling".format(
                    self._scrolling_index
                )
            )

    def fetch(self, refresh_url=None, timeout=10):
        """Fetch data from the url we initialized with, perfom any parsing,
        and display text or graphics. This function does pretty much everything
        Optionally update the URL
        """
        if refresh_url:
            self._url = refresh_url
        values = []

        values = self.network.fetch_data(
            self._url,
            headers=self._headers,
            json_path=self._json_path,
            regexp_path=self._regexp_path,
            timeout=timeout,
        )

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
                    lines = self.wrap_nicely(string, self._text_wrap[i])
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

    @property
    def url(self):
        """
        Get or set the URL of your data source.
        """
        return self._json_path

    @url.setter
    def url(self, value):
        self._url = value
        if value and not self.network.uselocal:
            self.network.connect()
            if self._debug:
                print("My IP address is", self.network.ip_address)

    @property
    def json_path(self):
        """
        Get or set the list of json traversal to get data out of. Can be list
        of lists for multiple data points.
        """
        return self._json_path

    @json_path.setter
    def json_path(self, value):
        if value:
            if isinstance(value[0], (list, tuple)):
                self._json_path = value
            else:
                self._json_path = (value,)
        else:
            self._json_path = None
