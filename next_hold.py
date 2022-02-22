"""
Get number of the remaining days on my library hold
"""

from seleniumwire import webdriver

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

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

    queueLength = driver.find_element(By.CLASS_NAME, "queueLength")
    print(queueLength.text)

    # Access and print requests via the `requests` attribute
    with open('lcpl.txt', 'w') as outfile:
        outfile.write(queueLength.text)
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
                        next_up = sorted([(hold['holdQueueLength'], hold['resource']['shortTitle']) for hold in status['holds']])
                        return next_up[0][0]

    return queueLength.text


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

# import requests
# import json
#
# """
# Get number of the remaining days on my library hold
# """
#
# login_url = 'https://catalog.library.loudoun.gov/login'
# status_url = 'https://catalog.library.loudoun.gov/requests/0/20/Status' #?_=1644544643458
#
#
# # Fill in your details here to be posted to the login form.
# payload = json.dumps({
#     'username': barcode,
#     'pin': p,
#     "rememberMe": True,
#     '': 'Cancel',
#     'password': p
# })
#
#
# # Use 'with' to ensure the session context is closed after use.
# with requests.Session() as s:
#     p = s.post(login_url, data=payload)
#     # print the html returned or something more intelligent to see if it's a successful login page.
#     print(p.text)
#
#     # An authorised request.
#     r = s.get(holds_url)
#     print(r.text)
#         # etc...