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
import json


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


def get_date(wt):
    '''
    Look up current date
    Return today and tomorrow in "m-d-yyyy" format
    :return:
    '''
    return '2-23-2022'
    

def get_entrees(requests, next_date):
    print(next_date)
    menu_base_url = secrets['school_lunch_api_url']

    payload = {
        'buildingId': secrets['school_lunch_buildingId'],
        'districtId': secrets['school_lunch_districtId'],
        "startDate": next_date,
        "endDate": next_date
    }

    url = '{}?{}'.format(menu_base_url, '&'.join(['{}={}'.format(key, payload[key]) for key in payload]))
    p = requests.get(url)
    menu = p.json()  # json.loads(p.text)
    for s in menu['FamilyMenuSessions']:
        if ('Lunch' in s.get('ServingSession', '')):
            menu = s['MenuPlans'][0]
    # print(menu['MenuPlanName'])
    ignore_words = {'Bagel', 'SunButter', 'Soybutter', 'Smoothie'}
    menu_items = {}
    for daily_menu in menu['Days']:
        entrees = [e['RecipeName'] for e in daily_menu['RecipeCategories'][0]['Recipes']]
        filtered_entrees = []
        for e in entrees:
            if len([w for w in e.split(' ') if w in ignore_words]) == 0:
                filtered_entrees.append(e)
        # print('{}: {}'.format(daily_menu.get('Date'), filtered_entrees))
        # menu_items[daily_menu.get('Date')] = filtered_entrees
    if len(filtered_entrees) == 0:
        return  ['Make your own lunch']
    # wrap menu text
    wrapped_menu = []
    this_line = ''
    for entree in filtered_entrees:
        for word in entree.split(' '):
            if len(this_line) > 0:
                this_line = this_line + ' '
            if len(this_line) + len(word) > 29:
                wrapped_menu.append(this_line)
                this_line = ''
            this_line = this_line + word
        if len(this_line) > 0:
            wrapped_menu.append(this_line)
        this_line = ''
    return  wrapped_menu

def update_display(ct, wt, q, m):
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
    # left-justified middle
    another_text.anchor_point = (-0.1, 0.5)
    another_text.anchored_position = (0, display.height // 2)
    main_group.append(another_text)
    
    # Add menu        
    another_text = label.Label(
        terminalio.FONT,
        scale=1,
        text='{} Lunch\n{}'.format(wt[:10], "\n".join(m)),
        color=0x000000,
        background_color=0xFFFFFF,
        padding_top=0,
        padding_bottom=0,
        padding_right=0,
        padding_left=0,
        line_spacing=1,
    )
    # left-justified middle
    another_text.anchor_point = (1.1, 0.5)
    another_text.anchored_position = (display.width, display.height // 2)
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
    
    menu = get_entrees(network, wake_time[:10])
    update_display(current_time, wake_time, queue, menu)
    magtag = MagTag()
    ding(magtag)
    magtag.exit_and_deep_sleep(sleep_duration)
