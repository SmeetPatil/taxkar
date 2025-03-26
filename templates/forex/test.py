with open('../../taxkar/forex_api_key.txt', 'r') as file:
    API_KEY = " ".join(line.rstrip() for line in file)
    print(API_KEY)

import datetime as dt
date = dt.datetime.now().strftime("%H:%M:%S %A,%d-%m-%Y")
print(date)