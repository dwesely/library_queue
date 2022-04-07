"""
Get number of the remaining days on my library hold
"""

from seleniumwire import webdriver

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException


from selenium.webdriver.common.by import By
from Adafruit_IO import Client, Feed, Data
import json
from secrets import secrets

def get_queue_length():
    holds_url = secrets['library_url']
    barcode = secrets['library_card']
    p = secrets['library_pin']

    driver = webdriver.Chrome()
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
                        next_up = sorted([(int(hold['holdQueueLength']), hold['resource']['shortTitle']) for hold in status['holds']])
                        return str(next_up[0][0])
                else:
                    print("No holdQueueLength")

    return queueText


def send_queue_update(q):
    ADAFRUIT_IO_USERNAME = secrets['aio_username']
    ADAFRUIT_IO_KEY = secrets['aio_key']
    aio = Client(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY)
    aio.send('nexthold', q)


if __name__ == '__main__':
    current_queue = get_queue_length()
    if current_queue:
        my_position = current_queue.split(' ')[0]
        send_queue_update(my_position)
    print(f'Complete, updated with queue {current_queue}')
