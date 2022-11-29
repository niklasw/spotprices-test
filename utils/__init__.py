from datetime import datetime


def log(msg):
    time = datetime.now().strftime('%Y%m%d-%H:%M:%S')
    print(f'{time:30s} {msg}')
