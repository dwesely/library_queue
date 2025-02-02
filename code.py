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
from pcf8563 import PCF8563
from tzdb import timezone

# Buttons
BTN_ELEM = 0
BTN_MID = 3
BTN_PREV = 1
BTN_NEXT = 2

weekday_text = {0: 'Mo', 1: 'Tu', 2: 'We', 3: 'Th', 4: 'Fr', 5: 'Sa', 6: 'Su'}

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
        response.close()
        # print(q)
        return q
    except BaseException:
        return -1


def get_current_time(requests, rtc):

    # Get our username, key and desired timezone
    aio_username = secrets["aio_username"]
    aio_key = secrets["aio_key"]
    location = secrets.get("timezone", None)
    fmt = "%Y-%m-%dT%H:%M"
    clock_time = rtc.datetime
    clock_datetime = datetime(*clock_time[0:7]) # convert date_struct to datetime

    if clock_time.tm_year < 2025: # module default is 2000-01-01
        ding(magtag, RED, 2) # indicate we are searching for an updated time
        TIME_URL = "https://io.adafruit.com/api/v2/%s/integrations/time/strftime?x-aio-key=%s&tz=%s" % (aio_username, aio_key, location)
        TIME_URL += "&fmt=%25Y-%25m-%25dT%25H%3A%25M"
        try:
            response = requests.get(TIME_URL)
            time_text = response.text
            response.close()

            # set the clock module for later
            date_object = datetime.fromisoformat(time_text)
            date_struct = [date_object.year, date_object.month, date_object.day, date_object.hour, date_object.minute, date_object.second, 0, -1, -1]
            rtc.datetime = time.struct_time(date_struct)
            return time_text
        except BaseException:
            return '2000-01-01T11:59'

    ding(magtag, GREEN, 3) # indicate the time has been read from the clock
    return clock_datetime.isoformat()


def get_events(requests, d, rtc, scroll):
    calendar_url = secrets['calendar_url']

    payload = {'start_date': d,
               'end_date': d,
               'id': secrets['calendar_id'],
               'section_ids': secrets['calendar_section_ids'],
               'paginate': 'false',
               'locale': 'en'}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

    url = '{}?{}'.format(calendar_url, '&'.join(['{}={}'.format(key, payload[key]) for key in payload]))

    try:
        p = requests.get(url)
    except:
       return ['Error: Unable to connect to school events.']

    try:
        calendar_data = p.json()  # json.loads(p.text)
    except ValueError:
       print(p.text)
       return ['Error: Events unparseable.']

    # sync date if needed, only on initial menu load
    if 'meta' in calendar_data and scroll == 0:
       if 'last_static_update' in calendar_data['meta']:
            clock_time = rtc.datetime
            clock_datetime = datetime(*clock_time[0:7]) # convert date_struct to datetime
            calendar_datetime = datetime.fromisoformat(calendar_data['meta']['last_static_update'][0:19])
            location = secrets.get("timezone", None)
            localtime = calendar_datetime + timezone(location).utcoffset(calendar_datetime)
            threshold = timedelta(minutes = 15)
            if (localtime < clock_datetime - threshold) or (localtime > clock_datetime + threshold):
                # menu update time is very far from current time, update the clock module
                ding(magtag, RED, 3) # indicate the clock is being set
                # time.sleep(10) # debugging
                date_struct = [localtime.year, localtime.month, localtime.day, localtime.hour, localtime.minute, localtime.second, 0, -1, -1]
                rtc.datetime = time.struct_time(date_struct)

    result = ''
    if 'events' in calendar_data:
        # continue grabbing daily events
        result = ', '.join({event['title'] for event in calendar_data['events'] if 'PTO MEETING' not in event['title'].upper()})
        if len(result)>29:
            result = '{}...'.format(result[:26])
    return result


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
        quote = response.text.replace('""','"').strip(',\r\n\t "')
        response.close()
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
            if '\n' in word:
                broken_word = word.split('\n')
                wrapped_quote.append(this_line + broken_word[0])
                this_line = '\n'.join(broken_word[1:])
            else:
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

    try:
        menu = p.json()  # json.loads(p.text)
    except ValueError:
       print(p.text)
       return ['Error: Menu unparseable.']

    if 'FamilyMenuSessions' in menu:
        for s in menu['FamilyMenuSessions']:
            if ('Lunch' in s.get('ServingSession', '')):
                menu = s['MenuPlans'][0]
                break
        # print(menu['MenuPlanName'])

    if 'MenuPlanName' not in menu:
        #return ['No menu, make your own lunch']
        return(get_top_quote(requests))
    ignore_words = {'Bagel', 'SunButter', 'Soybutter', 'Smoothie', 'OPTION:', 'Salad', 'Parfait', 'Wrap'}
    menu_items = {}
    for daily_menu in menu['Days']:
        entrees = [e['RecipeName'] for e in daily_menu['MenuMeals'][0]['RecipeCategories'][0]['Recipes']]
        filtered_entrees = []
        for e in entrees:
            if len([w for w in e.split(' ') if w in ignore_words]) == 0:
                filtered_entrees.append(e.replace(' - MS/HS', '').replace('Sandwich', 'SW').replace('with ', 'w/').replace('arella', '.'))
        # print('{}: {}'.format(daily_menu.get('Date'), filtered_entrees))
        # menu_items[daily_menu.get('Date')] = filtered_entrees
    del menu
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

def update_display(ct, wt, ld, wd, q, m, sn, v):
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
    if sn > 0:
        label_text = '---- {} {} Lunch ---\n{}'.format(wd, ld, "\n".join(m)).rstrip('\n\r\t ')
    else:
        label_text = '------- {} {} ------\n{}'.format(wd, ld, "\n".join(m)).rstrip('\n\r\t ')
    another_text = label.Label(
        menu_font,
        scale=params['m_scale'],
        text=label_text,
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
        text='{}      ->      {}'.format(ct[:16], wt[:16]),
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


    bg_for_school = {0:0xFFFFFF, 1: 0xFFFFFF, 2:0xFFFFFF}
    bg_for_school[sn] = 0x333333
    fg_for_school = {0:0xFFFFFF, 1: 0x000000, 2:0x000000}
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
    if v > 3.1:
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
    else:
        battery = label.Label(
            terminalio.FONT,
            text='LOW BATTERY',
            color=0xFFFFFF,
            background_color=0x000000,
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

def wake_up(device):
    '''
    Wake up the parts of the device we will be using
    '''
    device.peripherals.neopixel_disable = False

    # No brightness control, it actually draws more power than running default brightness:
    # https://learn.adafruit.com/circuitpython-essentials/circuitpython-neopixel
    # "You can drive 300 NeoPixel LEDs with brightness control
    #  (set brightness=1.0 in object creation) and 1000 LEDs without.
    #  That's because to adjust the brightness we have to dynamically
    #  recreate the data-stream each write.

    # device.peripherals.neopixels.brightness = 0.05

    '''
    Other power considerations:
    https://learn.adafruit.com/adafruit-magtag?view=all
    '''

def tuck_in(device):
    device.peripherals.buttons[BTN_ELEM].deinit()
    device.peripherals.buttons[BTN_MID].deinit()
    device.peripherals.neopixel_disable = True
    pass


def ding(device, color, blinks, audible=False, wait_for_button=False):
    def sweepright():
        for p in range(0, blinks):
            if p < blinks - 1:
                device.peripherals.neopixels[3 - p] = 0
            else:
                device.peripherals.neopixels[3 - p] = color
        if wait_for_button:
            scroll_pause_delay = time.time() + 20
            while time.time() < scroll_pause_delay:
                # debug
                if device.peripherals.button_b_pressed:
                    device.peripherals.neopixels[0] = 0
                    device.peripherals.neopixels[2] = color
                    return -1
                elif device.peripherals.button_c_pressed:
                    device.peripherals.neopixels[0] = 0
                    device.peripherals.neopixels[1] = color
                    return 1
                elif device.peripherals.button_d_pressed:
                    return 0
                elif device.peripherals.button_a_pressed:
                    return 0
        return 0
    if audible:
        d = 0.15
        device.peripherals.play_tone(440, d)
        device.peripherals.play_tone(880, d)
    pressed = sweepright()
    return pressed



if __name__ == '__main__':
    magtag = MagTag()

    # detect and set which school to display
    # set default then check if alternate button was pressed
    # Elementary Lunch (default)
    boodeep = False
    school_color = GREEN
    school_number = 0
    if isinstance(alarm.wake_alarm, alarm.pin.PinAlarm):
        boodeep = False
        if repr(alarm.wake_alarm.pin) == 'board.BUTTON_D':
            # Middle Lunch
            school_color = BURGUNDY
            school_number = 2
        else:
            school_color = LAVENDER
            school_number = 1

    wake_up(magtag)

    # Set up clock
    i2c_bus = board.I2C()
    rtc = PCF8563(i2c_bus)

    ding(magtag, school_color, 1)

    network = connect_to_wifi()
    ding(magtag, school_color, 2)
    queue = get_latest_queue(network)
    current_time = get_current_time(network, rtc)
    wake_time, sleep_duration = get_time_to_next_wake(current_time)

    time_alarm = alarm.time.TimeAlarm(monotonic_time=sleep_duration)

    scroll = 0
    lunch_time = wake_time
    checking_school = school_number > 0
    while True:
        if checking_school:
            if scroll != 0:
                lunch_time = (datetime.fromisoformat(lunch_time) + timedelta(days=scroll)).isoformat()
            lunch_date = lunch_time[:10]
            menu = get_entrees(network, lunch_date, f'school_lunch_buildingId{school_number}')
            if menu:
                menu.append(get_events(network, lunch_time[:10], rtc, scroll))
        else:
            menu = get_top_quote(network)
        # menu = ['blah', 'blah']
        ding(magtag, school_color, 3)

        voltage = magtag.peripherals.battery
        voltage = magtag.peripherals.battery
        lunch_date = lunch_time[:10]
        weekday = weekday_text[datetime.fromisoformat(lunch_time).weekday()]
        update_display(current_time, wake_time, lunch_date, weekday, queue, menu, school_number, voltage)
        scroll = ding(magtag, school_color, 4, boodeep, checking_school)
        if scroll == 0:
            break

    # Deinitialize pins and set wakeup alarms
    tuck_in(magtag)
    pin_alarm_left = alarm.pin.PinAlarm(pin=board.D15, value=False, pull=True)
    pin_alarm_right = alarm.pin.PinAlarm(pin=board.D11, value=False, pull=True)


    print(f'Current time {current_time}')
    print(f'Wake at {wake_time}')
    print(f'Sleep for {sleep_duration} ms')
    alarm.exit_and_deep_sleep_until_alarms(time_alarm, pin_alarm_left, pin_alarm_right)
    #alarm.exit_and_deep_sleep_until_alarms(time_alarm)

