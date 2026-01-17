import requests
import time
def main():
    url = "https://servercreation-62uc.onrender.com/credits/afk"

    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2OTZiOTVjZjE5ODNlNDkxMTFkNDhkNzkiLCJpYXQiOjE3Njg2NTgzODMsImV4cCI6MTc2OTI2MzE4M30.c_OmYNDTO0Kv4H5CHuILQTQKwxTnHt-zP4PsoEg6tgs",
        "content-type": "application/json",
        "priority": "u=1, i",
        "sec-ch-ua": "\"Not)A;Brand\";v=\"8\", \"Chromium\";v=\"138\", \"Google Chrome\";v=\"138\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site",
        "referer": "https://dash.lemonhost.me/"
    }

    session = requests.Session()

    while True:
        try:
            response = session.post(url, headers=headers, data=None)
            print("Status:", response.status_code)
            print("Response:", response.text)
        except Exception as e:
            print("Error:", e)

        time.sleep(30)
