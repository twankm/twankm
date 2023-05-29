
# E-Ink:
# - https://my.cytron.io/p-2.9-inch-e-ink-raw-display-panel-tri-color?tracking=idris
# - https://my.cytron.io/p-universal-e-paper-raw-panel-driver-hat?tracking=idris
#
# References:
# - https://learn.adafruit.com/2-13-in-e-ink-bonnet/usage
# - https://gist.github.com/ScientificProgrammer/bd08a1474c6e5f0a8f102b35ac2533f1

import time
import digitalio
import busio
import board
from PIL import Image, ImageDraw, ImageFont
from adafruit_epd.epd import Adafruit_EPD
from adafruit_epd.il0373 import Adafruit_IL0373

# First define some color constants
WHITE = (0xFF, 0xFF, 0xFF)
BLACK = (0x00, 0x00, 0x00)
RED = (0xFF, 0x00, 0x00)

# Next define some constants to allow easy resizing of shapes and colors
BORDER = 20
FONTSIZE = 24
BACKGROUND_COLOR = RED
FOREGROUND_COLOR = WHITE
TEXT_COLOR = BLACK

spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
ecs = digitalio.DigitalInOut(board.CE0)
dc = digitalio.DigitalInOut(board.D25)
rst = digitalio.DigitalInOut(board.D17)
busy = digitalio.DigitalInOut(board.D24)
srcs = None

display = Adafruit_IL0373(
    128, 296, spi,
    cs_pin=ecs,
    dc_pin=dc,
    sramcs_pin=srcs,
    rst_pin=rst,
    busy_pin=busy
)
display.rotation = 3

image = Image.new("RGB", (display.width, display.height))

# Get drawing object to draw on image.
draw = ImageDraw.Draw(image)

# Draw a filled box as the background
draw.rectangle(
    (0, 0, display.width, display.height),
    fill=BACKGROUND_COLOR
)

# Draw a smaller inner foreground rectangle
draw.rectangle(
    (BORDER, BORDER, display.width - BORDER - 1, display.height - BORDER - 1),
    fill=FOREGROUND_COLOR,
)

# Load a TTF Font
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", FONTSIZE)

# Draw Some Text
text = "Hello World!"
(font_width, font_height) = font.getsize(text)
draw.text(
    (display.width // 2 - font_width // 2, display.height // 2 - font_height // 2),
    text,
    font=font,
    fill=TEXT_COLOR,
)

# Display image.
display.image(image)
display.display()

time.sleep(180)

draw.rectangle(
    (0, 0, display.width, display.height),
    fill=FOREGROUND_COLOR
)

display.image(image)
display.display()