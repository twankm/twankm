from pynput.keyboard import Key, Listener

def on_press(key):
    print('{0} pressed'.format(key))

def on_release(key):
    print('{0} release'.format(key))
    if key == Key.esc:
        # Stop listener
        return False
    
with Listener(on_press=on_press) as listener:
    listener.join()