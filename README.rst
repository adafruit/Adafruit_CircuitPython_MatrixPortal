Introduction
============

.. image:: https://readthedocs.org/projects/adafruit-circuitpython-matrixportal/badge/?version=latest
    :target: https://circuitpython.readthedocs.io/projects/matrixportal/en/latest/
    :alt: Documentation Status

.. image:: https://img.shields.io/discord/327254708534116352.svg
    :target: https://adafru.it/discord
    :alt: Discord

.. image:: https://github.com/adafruit/Adafruit_CircuitPython_MatrixPortal/workflows/Build%20CI/badge.svg
    :target: https://github.com/adafruit/Adafruit_CircuitPython_MatrixPortal/actions
    :alt: Build Status

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black
    :alt: Code Style: Black

CircuitPython helper for Adafruit MatrixPortal M4, Adafruit RGB Matrix Shield + Metro M4 Airlift Lite,
and Adafruit RGB Matrix FeatherWings


Dependencies
=============
This driver depends on:

* `Adafruit CircuitPython <https://github.com/adafruit/circuitpython>`_

Please ensure all dependencies are available on the CircuitPython filesystem.
This is easily achieved by downloading
`the Adafruit library and driver bundle <https://circuitpython.org/libraries>`_.

Usage Example
=============

.. code:: python

    import time
    import board
    import terminalio
    from adafruit_matrixportal import MatrixPortal

    # You can display in 'GBP', 'EUR' or 'USD'
    CURRENCY = "USD"
    # Set up where we'll be fetching data from
    DATA_SOURCE = "https://api.coindesk.com/v1/bpi/currentprice.json"
    DATA_LOCATION = ["bpi", CURRENCY, "rate_float"]


    def text_transform(val):
        if CURRENCY == "USD":
            return "$%d" % val
        if CURRENCY == "EUR":
            return "‎€%d" % val
        if CURRENCY == "GBP":
            return "£%d" % val
        return "%d" % val


    # the current working directory (where this file is)
    cwd = ("/" + __file__).rsplit("/", 1)[0]

    matrixportal = MatrixPortal(
        url=DATA_SOURCE,
        json_path=DATA_LOCATION,
        status_neopixel=board.NEOPIXEL,
        debug=True,
    )

    matrixportal.add_text(
        text_font=terminalio.FONT,
        text_position=(16, 16),
        text_color=0xFFFFFF,
        text_transform=text_transform,
    )
    matrixportal.preload_font(b"$012345789")  # preload numbers
    matrixportal.preload_font((0x00A3, 0x20AC))  # preload gbp/euro symbol

    while True:
        try:
            value = matrixportal.fetch()
            print("Response is", value)
        except (ValueError, RuntimeError) as e:
            print("Some error occured, retrying! -", e)

        time.sleep(3 * 60)  # wait 3 minutes


Contributing
============

Contributions are welcome! Please read our `Code of Conduct
<https://github.com/adafruit/Adafruit_CircuitPython_MatrixPortal/blob/master/CODE_OF_CONDUCT.md>`_
before contributing to help this project stay welcoming.

Documentation
=============

For information on building library documentation, please check out `this guide <https://learn.adafruit.com/creating-and-sharing-a-circuitpython-library/sharing-our-docs-on-readthedocs#sphinx-5-1>`_.
