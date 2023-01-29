import json
import threading
from bot import create_bot

with open('config.json', 'r') as f:
    data = json.load(f)['data']
    for x in data:
        x['voice_channel_id'] = 0


def create_instance(token):
    create_bot(data, token)


if __name__ == "__main__":
    t1 = threading.Thread(target=create_instance, args=(data[0]['token'],))
    t1.start()
    t2 = threading.Thread(target=create_instance, args=(data[1]['token'],))
    t2.start()

    t1.join()
    t2.join()
