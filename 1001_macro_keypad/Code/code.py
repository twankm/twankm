print("Starting")

import board

from kmk.kmk_keyboard import KMKKeyboard
from kmk.keys import KC
from kmk.scanners import DiodeOrientation
from kmk.modules.layers import Layers
from kmk.modules.encoder import EncoderHandler
from kmk.modules.mouse_keys import MouseKeys
from kmk.modules.macros import Macros, Press, Release, Tap, Delay


import time
import busio
from lib.adafruit_display_text import label
from lib.adafruit_displayio_layout.layouts.grid_layout import GridLayout
import terminalio
import displayio
import lib.adafruit_ssd1675 as adafruit_ssd1675
import keymaps
import gc


keyboard = KMKKeyboard()
keyboard.debug_enabled = True

layers = Layers()
encoder_handler = EncoderHandler()
mouseKeys = MouseKeys()
macros = Macros()


keyboard.SCL=board.GP11
keyboard.SDA=board.GP10
keyboard.RES= board.GP12

keyboard.row_pins = (board.GP0,board.GP1,board.GP2, board.GP3)
keyboard.col_pins = (board.GP6,board.GP7,board.GP5, board.GP4)
keyboard.diode_orientation = DiodeOrientation.ROW2COL
encoder_handler.pins = (
    (board.GP10, board.GP9, board.GP8, False),
    (board.GP15, board.GP14, board.GP13, False),)

keyboard.keymap = keymaps.maps
current_layer = 0

total_layers = len(keyboard.keymap)


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

display = adafruit_ssd1675.SSD1675(
    display_bus, width=250, height=122,  busy_pin=epd_busy, rotation = 270, seconds_per_frame=1)



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
# text_area = []
txtGrp = displayio.Group()


grid_size = (3, 4)
layout = GridLayout(x = 0, y = 0, width = 180, height = 120, grid_size = grid_size, cell_padding = 6, v_divider_line_cols=(0,1,2,3,4), h_divider_line_rows=(0,1,2,3), divider_line_color=0x0)
layerLabel = label.Label(terminalio.FONT, color=0x0,scale = 2, x=0, y=0, text="Layer: 0", background_color=None)
layerLabel.x = 7
layerLabel.y = 108
g.append(layerLabel)
address = 0

def setText(_label):
    if len(_label.text) >= 4:
        _label.scale = 1
    else:
        _label.scale = 2

    if _label.bounding_box[2] > 10:
        _label.text = wrap_text(_label.text, 10)
    return _label

def wrap_text(text, max_length):
    return '\n'.join([text[i:i+max_length] for i in range(0, len(text), max_length)])

def assignKeyOnDisplay(gridSize, keyMap, _layout, address=0, _layer = 0):
    if _layout not in g:
        for row in range(0, gridSize[0]):
            for col in range(0, gridSize[1]):
                char = keyMap[_layer][address]
                lbl = label.Label(terminalio.FONT, color=0x0,scale = 2, x=0, y=0, text=char, background_color=None)
                setText(lbl)
                # _labels.append(lbl)
                _layout.add_content(lbl, grid_position=(col, row), cell_size=(1, 1))
                address += 1
        g.append(_layout)

    else:
        for row in range(0, gridSize[0]):
            for col in range(0, gridSize[1]):
                char = keyMap[_layer][address]
                cell = _layout.get_cell((col, row))
                cell.text = char
                setText(cell)
                address += 1
                gc.collect()
        layerLabel.text = "Layer: " + str(_layer)

    gc.collect()

    

    
assignKeyOnDisplay(grid_size, keymaps.layers, layout)
address = 0



grid_size = (1, 2)
layout1 = GridLayout(x = 120, y = 90, width = 60, height = 50, grid_size = grid_size, cell_padding = 6, v_divider_line_cols=(0,1,2), h_divider_line_rows=(0,1), divider_line_color=0x0)
assignKeyOnDisplay(grid_size, keymaps.layers, layout1, 12)


display.auto_refresh = False
display.root_group = g
display.refresh()
# displayio.release_displays()

    

def rotate_encoder(add=bool):
    
    def generator(keyboard):
        
        # global current_layer
        current_layer = keyboard.active_layers[0]
        if add:
            if current_layer >= total_layers - 1:
                return
            current_layer = (current_layer + 1)
        else:
            if current_layer == 0:
                return
            current_layer = (current_layer - 1)
        keyboard.active_layers = [current_layer]
        print(current_layer)
        time.sleep(0.1)
    
        assignKeyOnDisplay((3,4), keymaps.layers, layout, address=0, _layer = current_layer)
        assignKeyOnDisplay((1,2), keymaps.layers, layout1, address=12, _layer = current_layer)

    
        if display.auto_refresh is False:
            display.refresh()
    return generator




ROTARY_LEFT = KC.MACRO(
    gc.collect(),
    rotate_encoder(False),
)

ROTARY_RIGHT = KC.MACRO(
    gc.collect(),
    rotate_encoder(True),
)

encoder_handler.map = [(( ROTARY_LEFT, ROTARY_RIGHT, KC.N1), (KC.MW_UP, KC.MW_DOWN, KC.N2),),(( ROTARY_LEFT, ROTARY_RIGHT, KC.N1), (KC.MW_UP, KC.MW_DOWN, KC.N2),),(( ROTARY_LEFT, ROTARY_RIGHT, KC.N1), (KC.MW_UP, KC.MW_DOWN, KC.N2),),(( ROTARY_LEFT, ROTARY_RIGHT, KC.N1), (KC.MW_UP, KC.MW_DOWN, KC.N2),),(( ROTARY_LEFT, ROTARY_RIGHT, KC.N1), (KC.MW_UP, KC.MW_DOWN, KC.N2),),(( ROTARY_LEFT, ROTARY_RIGHT, KC.N1), (KC.MW_UP, KC.MW_DOWN, KC.N2),),]



keyboard.modules = [layers, encoder_handler, mouseKeys, macros]

print(keyboard.active_layers[0])
if __name__ == '__main__':
    keyboard.go()
