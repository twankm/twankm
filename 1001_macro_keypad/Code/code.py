print("Starting")

import board


from kmk.kmk_keyboard import KMKKeyboard
from kmk.keys import KC
from kmk.keys import ALL_ALPHAS, ALL_NUMBERS
from kmk.scanners import DiodeOrientation
from kmk.modules.layers import Layers
from kmk.modules.encoder import EncoderHandler


import time
import busio
from adafruit_display_text import label
from adafruit_display_shapes.circle import Circle
from adafruit_display_shapes.rect import Rect
from adafruit_displayio_layout.layouts.grid_layout import GridLayout
import terminalio
import displayio
import adafruit_ssd1675
from adafruit_epd.epd import Adafruit_EPD


keyboard = KMKKeyboard()
keyboard.debug_enabled = True

layers = Layers()
encoder_handler = EncoderHandler()

keyboard.SCL=board.GP11
keyboard.SDA=board.GP10
keyboard.RES= board.GP12

keyboard.row_pins = (board.GP0,board.GP1,board.GP2, board.GP3)
keyboard.col_pins = (board.GP6,board.GP7,board.GP5, board.GP4)
keyboard.diode_orientation = DiodeOrientation.ROW2COL
keyboard.modules = [encoder_handler]
encoder_handler.pins = (
    (board.GP10, board.GP9, board.GP8, False),
    (board.GP15, board.GP14, board.GP13, False),)

# keyboard.keymap = [
#     [KC.LCTL(KC.A), KC.PSCREEN, KC.N1, KC.P2,
#      KC.W, KC.G, KC.H, KC.R,
#      KC.K, KC.L, KC.Z, KC.Y,
#      KC.LCTL(KC.LSFT(KC.Z)), KC.LCTL(KC.Z) , KC.NO, KC.NO]
# ]
keyboard.keymap = [
    [KC.LCTL(KC.A), KC.PSCREEN, KC.N1, KC.P2, KC.W, KC.G, KC.H, KC.R, KC.K, KC.L, KC.Z, KC.Y, KC.LCTL(KC.LSFT(KC.Z)), KC.LCTL(KC.Z) , KC.NO, KC.NO]
]

encoder_handler.map = [( (KC.LEFT, KC.RIGHT, KC.N1), (KC.PGUP, KC.PGDOWN, KC.N2),),]



displayio.release_displays()

# This pinout works on a Feather M4 and may need to be altered for other boards.
spi = busio.SPI(board.GP18, board.GP19)  # Uses SCK and MOSI
epd_cs = board.GP20
epd_dc = board.GP16
epd_reset = board.GP17
epd_busy = board.GP21

display_bus = displayio.FourWire(
    spi, command=epd_dc, chip_select=epd_cs, reset=epd_reset, baudrate=1000000
)
time.sleep(1)

display = adafruit_ssd1675.SSD1675(
    display_bus, width=250, height=122, rotation=270, busy_pin=epd_busy
)


g = displayio.Group()

posx = 0
posy = 0
width = 50
height = 40

color_bitmap = displayio.Bitmap(250,122,1)
color_pallette = displayio.Palette(1)
color_pallette[0] = 0xFFFFFF
bg_sprite = displayio.TileGrid(color_bitmap, pixel_shader=color_pallette)

g.append(bg_sprite)

cnt = 0
text_area = []
txtGrp = displayio.Group()


grid_size = (3, 4)
layout = GridLayout(x = 1, y = 1, width = 180, height = 120, grid_size = grid_size, cell_padding = 4, v_divider_line_cols=(1,2,3,4,5), h_divider_line_rows=(1,2,3,4), divider_line_color=0x0)
_labels = []
address = 0
print(keyboard.active_layers[0])

for row in range(0, grid_size[0]):
    for col in range(0 , grid_size[1]):
        char = ""
        if 30 > keyboard.keymap[0][address].code >= 4:
            char = ALL_ALPHAS[keyboard.keymap[0][address].code-4]
        elif 40 > keyboard.keymap[0][address].code >= 30:
            char = ALL_NUMBERS[keyboard.keymap[0][address].code - 30]
        print(char)
        _labels.append(label.Label(terminalio.FONT, color= 0x0,scale=1, x=0, y=0, text = char, background_color=None))
        layout.add_content(_labels[address], grid_position=(col, row), cell_size= (1,1))
        address += 1
        

address = 0
keys = keyboard.keymap[0]

key_names = [str(k) for k in keys]
print(key_names)
g.append(layout)


display.auto_refresh = False
display.show(g)

display.refresh()

print("refreshed")

if __name__ == '__main__':
    keyboard.go()
