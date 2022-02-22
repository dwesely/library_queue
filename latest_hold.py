from Adafruit_IO import Client, Feed, Data
from secrets import secrets

def get_latest_queue():
    ADAFRUIT_IO_USERNAME = secrets['aio_username']
    ADAFRUIT_IO_KEY = secrets['aio_key']
    aio = Client(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY)
    q = aio.receive('nexthold').value
    return q


if __name__ == '__main__':
    my_position = get_latest_queue()
    print(f'Current queue position: {my_position}')