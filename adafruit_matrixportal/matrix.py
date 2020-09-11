# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams, written for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense
"""
`adafruit_matrixportal.matrix`
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

import board
import displayio
import rgbmatrix
import framebufferio


__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_MatrixPortal.git"


class Matrix:
    """Class representing the Adafruit RGB Matrix. This is used to automatically
    initialize the display.

    :param int width: The width of the display in Pixels. Defaults to 64.
    :param int height: The height of the display in Pixels. Defaults to 32.
    :param int bit_depth: The number of bits per color channel. Defaults to 2.
    :param list alt_addr_pins: An alternate set of address pins to use. Defaults to None

    """

    # pylint: disable=too-few-public-methods
    def __init__(self, *, width=64, height=32, bit_depth=2, alt_addr_pins=None):

        if alt_addr_pins is not None:
            addr_pins = alt_addr_pins
        else:
            addr_pins = [board.A0, board.A1, board.A2, board.A3]

        try:
            displayio.release_displays()
            matrix = rgbmatrix.RGBMatrix(
                width=width,
                height=height,
                bit_depth=bit_depth,
                rgb_pins=[board.D2, board.D3, board.D4, board.D5, board.D6, board.D7],
                addr_pins=addr_pins,
                clock_pin=board.A4,
                latch_pin=board.D10,
                output_enable_pin=board.D9,
            )
            self.display = framebufferio.FramebufferDisplay(matrix)
        except ValueError:
            raise RuntimeError("Failed to initialize RGB Matrix") from ValueError
