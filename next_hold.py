"""
Get number of the remaining days on my library hold
"""

from seleniumwire import webdriver

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import SessionNotCreatedException


from selenium.webdriver.common.by import By
from Adafruit_IO import Client, Feed, Data
import json
import random
import time
from secrets import secrets


def get_book_lists(urls, barcode, p):
    # get all overdue, pending pickup books, and hold positions

    book_lists = {} # overdue, ready, queued

    holds_url = urls['holds']
    loans_url = urls['loans']

    # Initialize connection
    try:
        driver = webdriver.Chrome()
    except SessionNotCreatedException:
        print(SessionNotCreatedException)
        return '88 Session not created, check Chromedriver version'
    except BaseException:
        return '99 Other error'

    # Use Holds page to log in
    driver.get(holds_url)
    driver.implicitly_wait(30)

    username = driver.find_element(By.ID, "barcode")
    password = driver.find_element(By.ID, "pin")
    username.send_keys(barcode)
    password.send_keys(p)

    action = ActionChains(driver)
    submit = driver.find_element(By.ID, "submitLoginFormButton")
    action.move_to_element(submit).click().perform()

    password = driver.find_element(By.ID, "pin")
    action.move_to_element(password).click().perform()
    password.send_keys(Keys.ENTER)

    queueText = ''
    print('--- Processing holds ---')

    try:
        queueLength = driver.find_element(By.CLASS_NAME, "queueLength")
        print(queueLength.text)
        queueText = queueLength.text
    except NoSuchElementException:
        print('No queueLength')
        queueText = '0 No holds detected in queue'

        # Access and print requests via the `requests` attribute
    with open('lcpl.txt', 'w') as outfile:
        outfile.write(queueText)
        outfile.write('\n')
        for request in driver.requests:
            if 'Status' in request.url: #request.response
                outfile.write('\n'.join([str(request.url),
                                         str(request.response.status_code),
                                         str(request.response.headers['Content-Type'])]))
                if b'holdQueueLength' in request.response.body:
                    status = json.loads(request.response.body.decode("utf-8"))
                    outfile.write('\n======\n')
                    outfile.write('\n======\n')
                    outfile.write('\n======\n')
                    outfile.write(str(request.response.body.decode("utf-8")))
                    outfile.write('\n======\n')
                    if 'holds' in status:
                        # If hold is in transit, add 1 so it only shows 0 if the hold is already at the library
                        next_up = sorted([(int(hold['holdQueueLength']) + int(hold['status']=='T'), hold['resource']['shortTitle'])
                                          for hold in status['holds'] if ((int(hold['holdQueueLength']) + int(hold['status']=='T')) > 0)])
                        for pos, title in next_up:
                            print(pos, title)
                        if len(next_up)>0:
                            book_lists['queued'] = next_up

                        # Record holds that are ready for pickup separately
                        ready = sorted([hold['resource']['shortTitle'] for hold in status['holds']
                                        if hold['status'] == 'AR'])
                        if len(ready)>0:
                            book_lists['ready'] = ready
                else:
                    print("No holdQueueLength")

    print(loans_url)

    # response_count = len(driver.requests)
    del driver.requests

    print('--- Processing loans ---')
    driver.get(loans_url)
    driver.implicitly_wait(30)
    time.sleep(10)
        # Access and print requests via the `requests` attribute
    with open('lcpl.txt', 'a') as outfile:
        outfile.write('\n')
        for request in driver.requests:
            if 'Status' in request.url: #request.response
                print(request.response.body)
                outfile.write('\n'.join([str(request.url),
                                         str(request.response.status_code),
                                         str(request.response.headers['Content-Type'])]))
                if b'shortTitle' in request.response.body:
                    status = json.loads(request.response.body.decode("utf-8"))
                    outfile.write('\n======\n')
                    outfile.write('\n======\n')
                    outfile.write('\n======\n')
                    outfile.write(str(request.response.body.decode("utf-8")))
                    outfile.write('\n======\n')
                    if 'loans' in status:
                        # Record loans that are overdue
                        overdue = sorted([loan['resource']['shortTitle'] for loan in status['loans'] if loan['status'] != None])
                        if len(overdue) > 0:
                            book_lists['overdue'] = overdue
                else:
                    print("No Loans")

    return book_lists


def get_queue_length():
    #print(get_book_lists(secrets['library_url'], secrets['library_cardpins'][0][0], secrets['library_cardpins'][0][1]))

    holds_url = secrets['library_url']['holds']
    barcode = secrets['library_cardpins'][0][0]
    p = secrets['library_cardpins'][0][1]

    try:
        driver = webdriver.Chrome()
    except SessionNotCreatedException:
        print(SessionNotCreatedException)
        return '88 Session not created, check Chromedriver version'
    except BaseException:
        return '99 Other error'
    driver.get(holds_url)
    driver.implicitly_wait(30)

    username = driver.find_element(By.ID, "barcode")
    password = driver.find_element(By.ID, "pin")
    username.send_keys(barcode)
    password.send_keys(p)

    action = ActionChains(driver)
    submit = driver.find_element(By.ID, "submitLoginFormButton")
    action.move_to_element(submit).click().perform()

    password = driver.find_element(By.ID, "pin")
    action.move_to_element(password).click().perform()
    password.send_keys(Keys.ENTER)

    queueText = ''

    try:
        queueLength = driver.find_element(By.CLASS_NAME, "queueLength")
        print(queueLength.text)
        queueText = queueLength.text
    except NoSuchElementException:
        print('No queueLength')
        queueText = '0 No holds detected in queue'

        # Access and print requests via the `requests` attribute
    with open('lcpl.txt', 'w') as outfile:
        outfile.write(queueText)
        outfile.write('\n')
        for request in driver.requests:
            if 'Status' in request.url: #request.response
                outfile.write('\n'.join([str(request.url),
                                         str(request.response.status_code),
                                         str(request.response.headers['Content-Type'])]))
                if b'holdQueueLength' in request.response.body:
                    status = json.loads(request.response.body.decode("utf-8"))
                    outfile.write('\n======\n')
                    outfile.write('\n======\n')
                    outfile.write('\n======\n')
                    outfile.write(str(request.response.body.decode("utf-8")))
                    outfile.write('\n======\n')
                    if 'holds' in status:
                        # If hold is in transit, add 1 so it only shows 0 if the hold is already at the library
                        next_up = sorted([(int(hold['holdQueueLength']) + int(hold['status']=='T'), hold['resource']['shortTitle'])
                                          for hold in status['holds']])
                        return str(next_up[0][0])
                else:
                    print("No holdQueueLength")

    return queueText


def send_queue_update(q, quote):
    ADAFRUIT_IO_USERNAME = secrets['aio_username']
    ADAFRUIT_IO_KEY = secrets['aio_key']
    aio = Client(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY)
    aio.send('nexthold', q)
    aio.send('qotd', quote)


def get_quote():
    file = 'quotes.json'
    with open(file, 'r') as f:
        quotes = json.load(f)
        todays_quote_data = random.choice(quotes)
        quote = '"{}" - {}'.format(todays_quote_data['text'], todays_quote_data['author'])
        return quote
    return ''


if __name__ == '__main__':
    quote = get_quote()
    print(quote)

    # get all hold and loan details
    combined_list = {}
    for card, pin in secrets['library_cardpins']:
        print(f'Processing: {card}')
        single_list = get_book_lists(secrets['library_url'], card, pin)
        for entry in single_list:
            if entry not in combined_list:
                combined_list[entry] = []
            combined_list[entry].extend(single_list[entry])
    print(combined_list)

    alternate_quote = ''
    my_position = '0'
    if 'overdue' in combined_list:
        overdue = ', '.join(combined_list['overdue'])
        alternate_quote = f'## OVERDUE ##: {overdue}'
    if 'ready' in combined_list:
        ready = ', '.join(combined_list['ready'])
        alternate_quote = f'{alternate_quote} \n ## READY ##: {ready}'
    if 'queued' in combined_list:
        next_up = sorted(combined_list['queued'])[0][1]
        my_position = str(sorted(combined_list['queued'])[0][0])
        alternate_quote = f'{alternate_quote} \nDONUT: {next_up}'
    print(alternate_quote)

    # current_queue = get_queue_length()
    #if current_queue:
        # my_position = current_queue.split(' ')[0]
    if alternate_quote:
        quote = alternate_quote
    send_queue_update(my_position, quote)
    print(f'Complete, updated with queue {my_position}')
