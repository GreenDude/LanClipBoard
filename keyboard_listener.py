from pynput import keyboard

PRESSED_KEYS = set()

def on_press(key):
    # print(f'Alphanumeric key {key.char} pressed')
    normalised_key = normalize_key(key)
    print(f"Pressed {normalised_key}")
    PRESSED_KEYS.add(normalised_key)

    my_paste_command = {"Key.cmd", "Key.shift", "v"}
    if my_paste_command <= PRESSED_KEYS:
        # Trigger paste
        print("YAY")
    else:
        print(PRESSED_KEYS)



def normalize_key(key):
    if hasattr(key, "char") and key.char:
        return key.char.lower()
    return str(key)


def on_release(key):
    normalised_key = normalize_key(key)
    print(f"Removed {normalised_key}")
    PRESSED_KEYS.remove(normalised_key)


# Collect events until released
with keyboard.Listener(
        on_press=on_press,
        on_release=on_release) as listener:
    listener.join()
