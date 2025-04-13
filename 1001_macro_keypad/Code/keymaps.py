from kmk.keys import KC
from kmk import keys
import json

fileName = "keymaps.json"
layers = []
with open(fileName, "r") as f:
    layers = json.load(f)
    # for layer in layers:
    #     layer[12], layer[13] = layer[13], layer[12]
    # print(layers[0][12])

    # print(layer)
# maps = [
#     [KC.LCTL(KC.get('S')), KC.F1, KC.W, KC.N2, KC.LALT(KC.LSHIFT(KC.W)), KC.A, KC.S, KC.D, KC.Z, KC.X, KC.C, KC.V, KC.SPACE, KC.LCTL(KC.Z) , KC.NO, KC.NO], [KC.LALT(KC.get('S')), KC.F, KC.W, KC.F2, KC.LALT(KC.LSHIFT(KC.W)), KC.G, KC.H, KC.R, KC.K, KC.L, KC.Z, KC.Y, KC.LCTL(KC.LSFT(KC.Z)), KC.LCTL(KC.Z) , KC.NO, KC.NO]
# ]
maps = []
for layer in layers:
    keyLayer  = []
    for key in layer:
        splittedKey = key.split("+")
        modifiers = []
        if "ALT" in splittedKey:
            splittedKey.remove("ALT")
            modifiers.append(1)
        if "CTRL" in splittedKey:
            splittedKey.remove("CTRL")
            modifiers.append(3)
        if "SHIFT" in splittedKey:
            splittedKey.remove("SHIFT")
            modifiers.append(4)

        key = KC.get(splittedKey[0])
        if 1 in modifiers:
            key = KC.LALT(key)

        if 3 in modifiers:
            key = KC.LCTRL(key)

        if 4 in modifiers:
            key = KC.LSFT(key)

        keyLayer.append(key)
        
    keyLayer[12], keyLayer[13] = keyLayer[13], keyLayer[12]
    maps.append(keyLayer)
# for map in layer[0]:
#     print(map)
#     # maps.append([KC.get(key) for key in map])wersdf