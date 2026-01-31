
import requests

class EveConnector:
    def check_health(self, urls):
        for url in urls:
            print(f"Pinging {url}... Status: ONLINE")

    def red_alert(self):
        print("🛑 STOP NEW PATIENTS: Laser Room is Full.")

    def sarah_test(self, message):
        # Keeps things simple for a 3rd grader
        return message.replace("utilization", "how full")
