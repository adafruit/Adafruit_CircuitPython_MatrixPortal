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
import terminalio
import displayio
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text.label import Label
from adafruit_matrixportal.network import Network
from adafruit_matrixportal.matrix import Matrix

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
        debug=False
    ):

        self._debug = debug
        matrix = Matrix(bit_depth=bit_depth, width=64, height=32)
        self.display = matrix.display

        self._network = Network(
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

        if self._debug:
            print("Init display")
        self.splash = displayio.Group(max_size=15)

        if self._debug:
            print("Init background")
        self._bg_group = displayio.Group(max_size=1)
        self._bg_file = None
        self._default_bg = default_bg
        self.splash.append(self._bg_group)

        # set the default background
        self.set_background(self._default_bg)
        self.display.show(self.splash)

        # Add any JSON translators
        if json_transform:
            self._network.ad.json_transform(json_transform)

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
        self.display.refresh()
        gc.collect()

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

    def get_local_time(self, location=None):
        """Accessor function for get_local_time()"""
        return self._network.get_local_time(location=location)

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
        values = []

        values = self._network.fetch_data(
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
        if value and not self._network.uselocal:
            self._network.connect()
            if self._debug:
                print("My IP address is", self._network.ip_address)

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
