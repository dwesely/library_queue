import neopixel
import alarm
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
from adafruit_bitmap_font import bitmap_font
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
    try:
        wifi.radio.connect(secrets["ssid"], secrets["password"])
        # print("Connected to %s!" % secrets["ssid"])
        # print("My IP address is", wifi.radio.ipv4_address)

        pool = socketpool.SocketPool(wifi.radio)
        requests = adafruit_requests.Session(pool, ssl.create_default_context())
        return requests
    except:
        print('Unable to connect to wifi.')
        return


def get_latest_queue(requests):
    # URLs to fetch from
    TEXT_URL = "https://io.adafruit.com/api/v2/%s/feeds/nexthold/data/retain" % secrets['aio_username']

    # print("Fetching text from", TEXT_URL)
    try:
        response = requests.get(TEXT_URL)
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
    TIME_URL = "https://io.adafruit.com/api/v2/%s/integrations/time/strftime?x-aio-key=%s&tz=%s" % (aio_username, aio_key, location)
    TIME_URL += "&fmt=%25Y-%25m-%25dT%25H%3A%25M"
    try:
        response = requests.get(TIME_URL)
        return response.text
    except BaseException:
        return '2000-01-01T00:00'


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


def get_top_quote(requests):
    # URLs to fetch from
    TEXT_URL = "https://io.adafruit.com/api/v2/%s/feeds/qotd/data/retain" % secrets['aio_username']

    # print("Fetching text from", TEXT_URL)
    try:
        response = requests.get(TEXT_URL)
        quote = response.text.strip(',\r\n\t ')[1:-1].replace('""','"')
        # print(quote)
        #Wrap the quote
        wrapped_quote = []
        this_line = ''
        for word in quote.split(' '):
            if len(this_line) > 0:
                this_line = this_line + ' '
            if len(this_line) + len(word) > 29:
                wrapped_quote.append(this_line)
                this_line = ''
            this_line = this_line + word
        if len(this_line) > 0:
            wrapped_quote.append(this_line.strip(' '))
        this_line = ''
        return wrapped_quote
    except BaseException:
        return ''


def get_entrees(requests, next_date, school):
    print(next_date)
    menu_base_url = secrets['school_lunch_api_url']

    payload = {
        'buildingId': secrets[school],
        'districtId': secrets['school_lunch_districtId'],
        "startDate": next_date,
        "endDate": next_date
    }

    url = '{}?{}'.format(menu_base_url, '&'.join(['{}={}'.format(key, payload[key]) for key in payload]))

    try:
        p = requests.get(url)
    except:
       return ['Error: Unable to connect to menu.']

    menu = p.json()  # json.loads(p.text)
    for s in menu['FamilyMenuSessions']:
        if ('Lunch' in s.get('ServingSession', '')):
            menu = s['MenuPlans'][0]
    # print(menu['MenuPlanName'])
    if 'MenuPlanName' not in menu:
        #return ['No menu, make your own lunch']
        return(get_top_quote(requests))
    ignore_words = {'Bagel', 'SunButter', 'Soybutter', 'Smoothie', 'OPTION:'}
    menu_items = {}
    for daily_menu in menu['Days']:
        entrees = [e['RecipeName'] for e in daily_menu['RecipeCategories'][0]['Recipes']]
        filtered_entrees = []
        for e in entrees:
            if len([w for w in e.split(' ') if w in ignore_words]) == 0:
                filtered_entrees.append(e.replace(' - MS/HS', '').replace('Sandwich', 'SW'))
        # print('{}: {}'.format(daily_menu.get('Date'), filtered_entrees))
        # menu_items[daily_menu.get('Date')] = filtered_entrees
    if len(filtered_entrees) == 0:
        return ['Make your own lunch']
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

def update_display(ct, wt, q, m, sn, v):
    # use built in display (PyPortal, PyGamer, PyBadge, CLUE, etc.)
    # see guide for setting up external displays (TFT / OLED breakouts, RGB matrices, etc.)
    # https://learn.adafruit.com/circuitpython-display-support-using-displayio/display-and-display-bus
    display = board.DISPLAY

    if q > 0:
        number_font = bitmap_font.load_font("/fonts/DejaVuSansMono-Bold-nums-88.bdf")
        menu_font = terminalio.FONT
        params = {'q_scale': 1, 'm_scale': 1}
    else:
        number_font = terminalio.FONT
        #https://github.com/Tecate/bitmap-fonts/blob/master/bitmap/unscii/unscii-16.pcf
        menu_font = bitmap_font.load_font("/fonts/unscii-16.pcf")
        params = {'q_scale': 2, 'm_scale': 1}

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
        number_font,
        scale=params['q_scale'],
        text="{0:02d}".format(q),
        color=0x000000,
        background_color=0xFFFFFF,
        padding_top=1,
        padding_bottom=3,
        padding_right=4,
        padding_left=4,
    )
    # left-justified middle, little below center
    another_text.anchor_point = (-0.1, 0.5)
    another_text.anchored_position = (0, (display.height // 2) + 10)
    main_group.append(another_text)

    # Add menu
    another_text = label.Label(
        menu_font,
        scale=params['m_scale'],
        text='_____ {} Lunch _____\n\n{}'.format(wt[:10], "\n".join(m)).rstrip('\n\r\t '),
        color=0x000000,
        background_color=0xFFFFFF,
        padding_top=0,
        padding_bottom=0,
        padding_right=0,
        padding_left=0,
        line_spacing=0.8,
    )
    # left-justified middle
    another_text.anchor_point = (1.0, 0.5)
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


    bg_for_school = {1: 0xFFFFFF, 2:0xFFFFFF}
    bg_for_school[sn] = 0x333333
    fg_for_school = {1: 0x000000, 2:0x000000}
    fg_for_school[sn] = 0xFFFFFF
    # school 1
    school_1 = label.Label(
        terminalio.FONT,
        text='Elementary',
        color=fg_for_school[1],
        background_color=bg_for_school[1],
        padding_top=0,
        padding_bottom=0,
        padding_right=3,
        padding_left=3,
    )
    school_1.anchor_point = (0.0, 1.0)
    school_1.anchored_position = (0.0, display.height)
    main_group.append(school_1)

    # school 2
    school_2 = label.Label(
        terminalio.FONT,
        text='Middle',
        color=fg_for_school[2],
        background_color=bg_for_school[2],
        padding_top=0,
        padding_bottom=0,
        padding_right=3,
        padding_left=3,
    )
    school_2.anchor_point = (2.0, 1.0)
    school_2.anchored_position = (display.width, display.height)
    main_group.append(school_2)


    # battery status
    battery = label.Label(
        terminalio.FONT,
        text='{:.2f}v'.format(v),
        color=0x000000,
        background_color=0xFFFFFF,
        padding_top=0,
        padding_bottom=0,
        padding_right=3,
        padding_left=3,
    )
    battery.anchor_point = (0.5, 1.0)
    battery.anchored_position = (display.width/2, display.height)
    main_group.append(battery)

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
BURGUNDY = 0x870A30
LAVENDER = 0x7c4fef # 0x9370DB


def ding(device, color, blinks, audible=False):
    def sweepright():
        device.peripherals.neopixel_disable = False
        device.peripherals.neopixels.brightness = 0.05
        for p in range(0, blinks):
            if p < blinks - 1:
                device.peripherals.neopixels[3 - p] = 0
            else:
                device.peripherals.neopixels[3 - p] = color
        if blinks > 3:
            time.sleep(2)
            device.peripherals.neopixel_disable = True
    if audible:
        d = 0.15
        device.peripherals.play_tone(440, d)
        device.peripherals.play_tone(880, d)
    sweepright()



if __name__ == '__main__':
    magtag = MagTag()

    # detect and set which school to display
    # set default then check if alternate button was pressed
    # Elementary Lunch (default)
    school_color = LAVENDER
    school_number = 1
    boodeep = True
    if isinstance(alarm.wake_alarm, alarm.pin.PinAlarm):
        if repr(alarm.wake_alarm.pin) == 'board.BUTTON_D':
            # Middle Lunch
            school_color = BURGUNDY
            school_number = 2
            boodeep = False
    ding(magtag, school_color, 1)

    network = connect_to_wifi()
    ding(magtag, school_color, 2)
    queue = get_latest_queue(network)
    current_time = get_current_time(network)
    wake_time, sleep_duration = get_time_to_next_wake(current_time)

    time_alarm = alarm.time.TimeAlarm(monotonic_time=sleep_duration)

    menu = get_entrees(network, wake_time[:10], f'school_lunch_buildingId{school_number}')
    ding(magtag, school_color, 3)

    voltage = magtag.peripherals.battery
    voltage = magtag.peripherals.battery
    update_display(current_time, wake_time, queue, menu, school_number, voltage)
    ding(magtag, school_color, 4, boodeep)
    # magtag.exit_and_deep_sleep(sleep_duration)

    # Deinitialize pins and set wakeup alarms
    magtag.peripherals.buttons[0].deinit()
    magtag.peripherals.buttons[3].deinit()
    pin_alarm_mtv = alarm.pin.PinAlarm(pin=board.D15, value=False, pull=True)
    pin_alarm_br = alarm.pin.PinAlarm(pin=board.D11, value=False, pull=True)
    alarm.exit_and_deep_sleep_until_alarms(time_alarm, pin_alarm_mtv, pin_alarm_br)
