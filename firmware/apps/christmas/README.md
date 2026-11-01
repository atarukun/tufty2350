# Christmas Countdown for Tufty

Counts down the days until Christmas, with falling snow, and shows today's date.

> [!NOTE]
> This app requires internet access! Add your network details to 'secrets.py' before using the app.

The badge forgets the date when its clocks run down, so on launch the app connects to WiFi, fetches the current time from an NTP server and converts it to your local time using `REGION` and `TIMEZONE` from `secrets.py`. The result is written to the battery-backed RTC, so other apps (such as the clock) see the correct local time too.

## secrets.py

```python
WIFI_SSID = "my-network"
WIFI_PASSWORD = "super-secret-password"
REGION = "eu"     # Options are us, cuba, eu, moldova, lebanon, egypt, chile, australia, nz
TIMEZONE = 0      # Offset from GMT as number of hours, i.e. 0, 1, -7 etc.
```

## Buttons/Controls:

### HOME
Return to the menu.
