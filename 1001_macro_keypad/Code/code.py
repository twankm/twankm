print("Starting")

import board


from kmk.kmk_keyboard import KMKKeyboard
from kmk.keys import KC
from kmk.scanners import DiodeOrientation
from kmk.modules.layers import Layers
from kmk.modules.encoder import EncoderHandler
from kmk.handlers.sequences import simple_key_sequence


import time
import busio
from lib.adafruit_display_text import label
from lib.adafruit_displayio_layout.layouts.grid_layout import GridLayout
import terminalio
import displayio
import lib.adafruit_ssd1675 as adafruit_ssd1675
import keymaps


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

keyboard.keymap = keymaps.maps

def rotate_encoder_left():
    print("Left Encoder Rotated Left")

def rotate_encoder_right():
    print("Left Encoder Rotated Right")

# TO_LAYER_1 = simple_key_sequence((KC.TO(1),))
# TO_LAYER_2 = simple_key_sequence((KC.TO(2),))
    
encoder_handler.map = [(( KC.LEFT, KC.RIGHT, KC.N1), (KC.PGUP, KC.PGDN, KC.N2),),]



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
layout = GridLayout(x = 0, y = 0, width = 180, height = 120, grid_size = grid_size, cell_padding = 6, v_divider_line_cols=(0,1,2,3,4), h_divider_line_rows=(0,1,2,3), divider_line_color=0x0)
_labels = []
address = 0



def wrap_text(text, max_length):
    return '\n'.join([text[i:i+max_length] for i in range(0, len(text), max_length)])

def assignKeyOnDisplay(gridSize, keyMap, _layout, address=0, _layer = 0):
    for row in range(0, gridSize[0]):
        for col in range(0, gridSize[1]):
            char = keyMap[_layer][address]
            scal = int(2)
            if len(char) >= 4:
                scal = 1

            lbl = label.Label(terminalio.FONT, color=0x0, scale=scal, x=0, y=0, text=char, background_color=None)
            if lbl.bounding_box[2] > 10:
                lbl.text = wrap_text(lbl.text, 10)
            _labels.append(lbl)
            _layout.add_content(_labels[address], grid_position=(col, row), cell_size=(1, 1))
            address += 1

assignKeyOnDisplay(grid_size, keymaps.layers, layout)
address = 0

g.append(layout)

grid_size = (1, 2)
layout1 = GridLayout(x = 120, y = 90, width = 60, height = 50, grid_size = grid_size, cell_padding = 6, v_divider_line_cols=(0,1,2), h_divider_line_rows=(0,1), divider_line_color=0x0)
assignKeyOnDisplay(grid_size, keymaps.layers, layout1, 12)
g.append(layout1)
display.auto_refresh = False
display.root_group = g
display.refresh()

print("refreshed")

if __name__ == '__main__':
    keyboard.go()
