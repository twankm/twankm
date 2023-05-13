from machine import Pin
from utime import sleep

# pin = Pin("LED", Pin.OUT)

# print("LED starts flashing...")
# while True:
#     pin.toggle()
#     sleep(.1) # sleep 1sec

pins = [
    Pin(17,Pin.OUT),
    Pin(16,Pin.OUT),
    Pin(14,Pin.OUT),
    Pin(13,Pin.OUT),
    Pin(12,Pin.OUT),
    Pin(18,Pin.OUT),
    Pin(19,Pin.OUT),
    Pin(15,Pin.OUT),
]
chars = [
    [1, 1, 1, 1, 1, 1, 0, 0],#0
    [0, 1, 1, 0, 0, 0, 0, 0],#1
    [1, 1, 0, 1, 1, 0, 1, 0],#2
    [1, 1, 1, 1, 0, 0, 1, 0],#3
    [0, 1, 1, 0, 0, 1, 1, 0],#4
    [1, 0, 1, 1, 0, 1, 1, 0],#5
    [1, 0, 1, 1, 1, 1, 1, 0],#6
    [1, 1, 1, 0, 0, 1, 0, 0],#7
    [1, 1, 1, 1, 1, 1, 1, 0],#8
    [1, 1, 1, 1, 0, 1, 1, 0],#9
]

def clear():
    for i in pins:
        i.value(1)

clear()
print("testing")
while True:
    for i in range(len(chars)):
        for j in range(len(pins)):
            pins[j].value(chars[i][j])

        print(i)

        sleep(.1)
