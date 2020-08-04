# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams, written for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense
"""
`adafruit_matrixportal.wifi`
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
import board
import busio
from digitalio import DigitalInOut
import neopixel
from adafruit_esp32spi import adafruit_esp32spi, adafruit_esp32spi_wifimanager

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_MatrixPortal.git"


class WiFi:
    """Class representing the ESP.

    :param status_neopixel: The pin for the status NeoPixel. Use ``board.NEOPIXEL`` for the on-board
                            NeoPixel. Defaults to ``None``, not the status LED
    :param esp: A passed ESP32 object, Can be used in cases where the ESP32 chip needs to be used
                             before calling the pyportal class. Defaults to ``None``.
    :param busio.SPI external_spi: A previously declared spi object. Defaults to ``None``.

    """

    def __init__(self, *, status_neopixel=None, esp=None, external_spi=None):

        if status_neopixel:
            self.neopix = neopixel.NeoPixel(status_neopixel, 1, brightness=0.2)
        else:
            self.neopix = None
        self.neo_status(0)

        if esp:  # If there was a passed ESP Object
            self.esp = esp
            if external_spi:  # If SPI Object Passed
                spi = external_spi
            else:  # Else: Make ESP32 connection
                spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
        else:
            esp32_ready = DigitalInOut(board.ESP_BUSY)
            esp32_gpio0 = DigitalInOut(board.ESP_GPIO0)
            esp32_reset = DigitalInOut(board.ESP_RESET)
            esp32_cs = DigitalInOut(board.ESP_CS)
            spi = busio.SPI(board.SCK, board.MOSI, board.MISO)

            self.esp = adafruit_esp32spi.ESP_SPIcontrol(
                spi, esp32_cs, esp32_ready, esp32_reset, esp32_gpio0
            )

        gc.collect()

    def neo_status(self, value):
        """The status NeoPixel.

        :param value: The color to change the NeoPixel.

        """
        if self.neopix:
            self.neopix.fill(value)

    def manager(self, secrets):
        """Initialize and return the WiFi Manager"""
        return adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(self.esp, secrets, None)
