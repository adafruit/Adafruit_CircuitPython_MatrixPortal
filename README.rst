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
    from adafruit_matrixportal.matrixportal import MatrixPortal

    # --- Display setup ---
    matrixportal = MatrixPortal(status_neopixel=board.NEOPIXEL, debug=True)

    # Create a new label with the color and text selected
    matrixportal.add_text(
        text_font=terminalio.FONT,
        text_position=(0, (matrixportal.graphics.display.height // 2) - 1),
        scrolling=True,
    )

    SCROLL_DELAY = 0.03

    contents = [
        { 'text': 'THIS IS RED',  'color': '#cf2727'},
        { 'text': 'THIS IS BLUE', 'color': '#0846e4'},
    ]

    while True:
        for content in contents:
            matrixportal.set_text(content['text'])

            # Set the text color
            matrixportal.set_text_color(content['color'])

            # Scroll it
            matrixportal.scroll_text(SCROLL_DELAY)

Contributing
============

Contributions are welcome! Please read our `Code of Conduct
<https://github.com/adafruit/Adafruit_CircuitPython_MatrixPortal/blob/master/CODE_OF_CONDUCT.md>`_
before contributing to help this project stay welcoming.

Documentation
=============

For information on building library documentation, please check out `this guide <https://learn.adafruit.com/creating-and-sharing-a-circuitpython-library/sharing-our-docs-on-readthedocs#sphinx-5-1>`_.
