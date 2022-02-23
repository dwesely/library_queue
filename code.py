import ipaddress
import ssl
import wifi
import socketpool
import adafruit_requests
from adafruit_datetime import datetime, timedelta
import time
import board
import displayio
import terminalio
from adafruit_display_text import label
from adafruit_magtag.magtag import MagTag


# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

def connect_to_wifi():
    # print("Connecting to %s" % secrets["ssid"])
    wifi.radio.connect(secrets["ssid"], secrets["password"])
    # print("Connected to %s!" % secrets["ssid"])
    # print("My IP address is", wifi.radio.ipv4_address)

    pool = socketpool.SocketPool(wifi.radio)
    requests = adafruit_requests.Session(pool, ssl.create_default_context())

    return requests


def get_latest_queue(requests):
    # URLs to fetch from
    TEXT_URL = "https://io.adafruit.com/api/v2/%s/feeds/nexthold/data/retain" % secrets['aio_username']

    # print("Fetching text from", TEXT_URL)
    response = requests.get(TEXT_URL)
    try:
        q = int(response.text.split(',')[0])
        # print(q)
        return q
    except BaseException:
        return -1


def get_current_time(requests):

    # Get our username, key and desired timezone
    aio_username = secrets["aio_username"]
    aio_key = secrets["aio_key"]
    location = secrets.get("timezone", None)
    TIME_URL = "https://io.adafruit.com/api/v2/%s/integrations/time/strftime?x-aio-key=%s" % (aio_username, aio_key)
    TIME_URL += "&fmt=%25Y-%25m-%25dT%25H%3A%25M"
    response = requests.get(TIME_URL)
    return response.text


def get_time_to_next_wake(current_time):
    ct = datetime.fromisoformat(current_time)
    wt = ct
    if ct.hour < 12:
        # this is a morning wake up, wait until the afternoon
        wt = datetime(ct.year, ct.month, ct.day, 17, 30)
        # print('It is morning, wake up at %s' % wt.isoformat())
    else:
        wt = datetime(ct.year, ct.month, ct.day, 6, 30) + timedelta(days=1)
        # print('It is afternoon, wake up at %s' % wt.isoformat())

    diff = (wt - ct).total_seconds()
    # print(ct.isoformat())
    # print('Sleep for %s seconds.' % diff)

    return wt.isoformat(), diff


def update_display(ct, wt, q):
    # use built in display (PyPortal, PyGamer, PyBadge, CLUE, etc.)
    # see guide for setting up external displays (TFT / OLED breakouts, RGB matrices, etc.)
    # https://learn.adafruit.com/circuitpython-display-support-using-displayio/display-and-display-bus
    display = board.DISPLAY

    # wait until we can draw
    time.sleep(display.time_to_refresh)

    # main group to hold everything
    main_group = displayio.Group()

    # white background. Scaled to save RAM
    bg_bitmap = displayio.Bitmap(display.width // 8, display.height // 8, 1)
    bg_palette = displayio.Palette(1)
    bg_palette[0] = 0xFFFFFF
    bg_sprite = displayio.TileGrid(bg_bitmap, x=0, y=0, pixel_shader=bg_palette)
    bg_group = displayio.Group(scale=8)
    bg_group.append(bg_sprite)
    main_group.append(bg_group)

    # Remaining Queue
    another_text = label.Label(
        terminalio.FONT,
        scale=8,
        text="{}".format(q),
        color=0x000000,
        background_color=0xFFFFFF,
        padding_top=1,
        padding_bottom=3,
        padding_right=4,
        padding_left=4,
    )
    # centered
    another_text.anchor_point = (0.5, 0.5)
    another_text.anchored_position = (display.width // 2, display.height // 2)
    main_group.append(another_text)


    # Last update time
    text_area = label.Label(
        terminalio.FONT,
        text='{}      ->      {}'.format(ct, wt[:16]),
        color=0xFFFFFF,
        background_color=0x666666,
        padding_top=1,
        padding_bottom=3,
        padding_right=4,
        padding_left=4,
    )
    text_area.x = 10
    text_area.y = 14
    main_group.append(text_area)

    # show the main group and refresh.
    display.show(main_group)
    display.refresh()
    time.sleep(2)


RED = 0x880000
GREEN = 0x008800
BLUE = 0x000088
YELLOW = 0x884400
CYAN = 0x0088BB
MAGENTA = 0x9900BB
WHITE = 0x888888


def ding(device):
    def blink(color, duration):
        device.peripherals.neopixel_disable = False
        device.peripherals.neopixels.fill(color)
        time.sleep(duration)
        device.peripherals.neopixel_disable = True
    d = 0.15
    device.peripherals.play_tone(440, d)
    device.peripherals.play_tone(880, d)
    blink(RED, 0.2)
    blink(YELLOW, 0.2)
    blink(GREEN, 0.2)
    blink(CYAN, 0.2)
    blink(BLUE, 0.2)
    blink(MAGENTA, 0.2)


if __name__ == '__main__':
    network = connect_to_wifi()
    queue = get_latest_queue(network)
    current_time = get_current_time(network)
    wake_time, sleep_duration = get_time_to_next_wake(current_time)
    update_display(current_time, wake_time, queue)
    magtag = MagTag()
    ding(magtag)
    magtag.exit_and_deep_sleep(sleep_duration)
