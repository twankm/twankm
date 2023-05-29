"""
A simple example showing how to read values from a rotary encoder

Requires the RotaryIRQ library from https://github.com/miketeachman/micropython-rotary
"""

from rotary_irq_rp2 import RotaryIRQ


# Enter the two GPIO pins you connected to data pins A and B
# Note the order of the pins isn't strict, swapping the pins
# will swap the direction of change.
rotary = RotaryIRQ(14, 15)

# If you're using a Standalone Rotary Encoder instead of a module,
# you might need to enable the internal pull-ups on the Pico
# rotary = RotaryIRQ(14, 15, pull_up=True)

current_val = 0  # Track the last known value of the encoder
while True:
    new_val = rotary.value()  # What is the encoder value right now?
    
    if current_val != new_val:  # The encoder value has changed!
        print('Encoder value:', new_val)  # Do something with the new value
        
        current_val = new_val  # Track this change as the last know value