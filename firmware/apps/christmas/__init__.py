# Christmas Countdown
#
# Counts down the days until 25 December with gently falling snow.
#
# The badge forgets the date whenever its clocks run down, so this app
# connects to WiFi, fetches the time from an NTP server, converts it to
# local time using REGION and TIMEZONE from secrets.py, and writes it to
# both the RP2350 clock and the battery-backed RTC.
#
# Ported from the Badger 2350 version:
# https://github.com/badger/home/pull/47

# Your app's directory
APP_DIR = "/system/apps/christmas"

import os
import sys

# Standalone bootstrap for finding app assets
os.chdir(APP_DIR)

# Standalone bootstrap for module imports
sys.path.insert(0, APP_DIR)

import random
import time

import ntptime
import secrets
import wifi
from daylightsaving import DaylightSaving, DaylightSavingPolicy
from machine import RTC

# Use the full 320x240 display
badge.mode(HIRES | VSYNC)

secrets.require("WIFI_SSID", "REGION", "TIMEZONE")

# Daylight saving rules, shared with the clock app.
# "zonename": (hemisphere, week, month, weekday, hour, week, month, weekday, hour, minutes clocks change by)
REGIONS = {
    "us": (0, 2, 3, 6, 2, 1, 11, 6, 2, 60),
    "cuba": (0, 2, 3, 6, 0, 1, 11, 6, 1, 60),
    "eu": (0, 0, 3, 6, 1, 0, 10, 6, 1, 60),
    "moldova": (0, 0, 3, 6, 2, 0, 10, 6, 3, 60),
    "lebanon": (0, 0, 3, 6, 0, 0, 10, 6, 0, 60),
    "egypt": (0, 0, 4, 4, 0, 0, 10, 3, 24, 60),
    "chile": (1, 1, 9, 5, 24, 1, 4, 5, 24, 60),
    "australia": (1, 1, 10, 6, 2, 1, 4, 6, 3, 60),
    "nz": (1, 0, 9, 6, 2, 1, 4, 6, 3, 60),
}

if secrets.REGION not in REGIONS:
    fatal_error("Unknown REGION!", f"Put your badge into disk mode (tap RESET twice)\nEdit 'secrets.py' and set REGION to one of:\n{', '.join(sorted(REGIONS))}")

# Colours
BG_COLOR = color.rgb(10, 20, 40)          # Dark blue night sky
TEXT_COLOR = color.rgb(255, 255, 255)     # White text
SHADOW_COLOR = color.rgb(0, 0, 0, 120)    # Soft text shadow
SNOWFLAKE_COLOR = color.rgb(240, 248, 255)

# Fonts and pixel-font scale factors for the 320x240 display
LARGE_FONT = font.ziplock
LARGE_SCALE = 3
SMALL_FONT = font.nope
SMALL_SCALE = 2
TINY_SCALE = 1

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

SECONDS_PER_DAY = 24 * 60 * 60

# How long to wait between NTP attempts, in milliseconds
SYNC_RETRY_INTERVAL = 5 * 1000


class Snowflake:
    """A single falling snowflake"""

    def __init__(self):
        self.reset()
        # Scatter the initial flakes over the whole screen rather than
        # dropping them all in from the top at once.
        self.y = random.uniform(0, screen.height)

    def reset(self):
        """Reset snowflake to above the top of the screen with random properties"""
        self.x = random.uniform(0, screen.width)
        self.y = random.uniform(-40, 0)
        self.size = random.randint(1, 3)
        self.speed = random.uniform(20, 50)   # pixels per second
        self.drift = random.uniform(-10, 10)  # pixels per second

    def update(self):
        """Move the snowflake, independent of frame rate"""
        dt = badge.ticks_delta / 1000
        self.y += self.speed * dt
        self.x += self.drift * dt

        if self.y > screen.height + self.size:
            self.reset()

        # Wrap horizontally
        if self.x < 0:
            self.x += screen.width
        elif self.x > screen.width:
            self.x -= screen.width

    def draw(self):
        screen.pen = SNOWFLAKE_COLOR
        screen.shape(shape.circle(int(self.x), int(self.y), self.size))


snowflakes = [Snowflake() for _ in range(40)]


class AppState:
    ConnectWiFi = 0
    SyncTime = 1
    Running = 2


app_state = AppState.ConnectWiFi
next_sync_at = 0
sync_attempts = 0


def build_daylight_saving():
    """Build the daylight saving calculator from REGION and TIMEZONE in secrets.py"""
    timezone_minutes = secrets.TIMEZONE * 60
    hemisphere, week_in, month_in, weekday_in, hour_in, week_out, month_out, weekday_out, hour_out, mins_difference = REGIONS[secrets.REGION]

    dstp = DaylightSavingPolicy(hemisphere, week_in, month_in, weekday_in, hour_in, timezone_minutes + mins_difference)
    stdp = DaylightSavingPolicy(hemisphere, week_out, month_out, weekday_out, hour_out, timezone_minutes)

    return DaylightSaving(dstp, stdp)


daylight_saving = build_daylight_saving()


def sync_time():
    """
    Fetch UTC from an NTP server, convert it to local time and store it in
    both the RP2350 clock and the battery-backed RTC.
    Returns True on success, False if the NTP request failed.
    """
    try:
        ntptime.settime()
    except OSError as e:
        print(f"NTP sync failed: {e}")
        return False

    utc = time.mktime(time.gmtime())
    tm = time.gmtime(daylight_saving.localtime(utc))

    # machine.RTC wants (year, month, day, weekday, hour, minute, second, subsecond)
    RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))

    # Keep the battery-backed RTC in step so the date survives a reboot
    rtc.localtime_to_rtc()

    print("NTP time sync successful")
    return True


def current_date():
    """Return today's local date as (year, month, day)"""
    year, month, day = time.localtime()[0:3]
    return year, month, day


def format_date(year, month, day):
    """Format a date as DD MMM YYYY, e.g. 25 Dec 2026"""
    return f"{day:02d} {MONTH_NAMES[month - 1]} {year}"


def days_until_christmas(year, month, day):
    """Whole days from the given date until the next 25 December"""
    christmas_year = year if (month, day) <= (12, 25) else year + 1

    today = time.mktime((year, month, day, 0, 0, 0, 0, 0))
    christmas = time.mktime((christmas_year, 12, 25, 0, 0, 0, 0, 0))

    return (christmas - today) // SECONDS_PER_DAY


def center_text(message, y, scale):
    """Draw text horizontally centred with a soft drop shadow, returning its height"""
    w, h = screen.measure_text(message, scale)
    x = (screen.width - w) // 2

    screen.pen = SHADOW_COLOR
    screen.text(message, x + scale, y + scale, scale)
    screen.pen = TEXT_COLOR
    screen.text(message, x, y, scale)

    return h


def draw_snow():
    for snowflake in snowflakes:
        snowflake.update()
        snowflake.draw()


def draw_status(message):
    """A single centred line, used while connecting and syncing"""
    screen.font = SMALL_FONT
    _, h = screen.measure_text(message, SMALL_SCALE)
    center_text(message, (screen.height - h) // 2, SMALL_SCALE)


def draw_countdown():
    year, month, day = current_date()
    days = days_until_christmas(year, month, day)

    y = 36

    if days == 0:
        screen.font = LARGE_FONT
        y += center_text("Merry", y, LARGE_SCALE) + 8
        y += center_text("Christmas!", y, LARGE_SCALE)
    else:
        screen.font = LARGE_FONT
        y += center_text(str(days), y, LARGE_SCALE) + 16

        screen.font = SMALL_FONT
        y += center_text("day until" if days == 1 else "days until", y, SMALL_SCALE) + 6
        y += center_text("Christmas", y, SMALL_SCALE)

    # Today's date along the bottom
    screen.font = SMALL_FONT
    date_text = format_date(year, month, day)
    _, h = screen.measure_text(date_text, TINY_SCALE)
    center_text(date_text, screen.height - h - 12, TINY_SCALE)


def update():
    global app_state, next_sync_at, sync_attempts

    screen.pen = BG_COLOR
    screen.clear()

    draw_snow()

    if app_state == AppState.ConnectWiFi:
        draw_status(f"Connecting to {secrets.WIFI_SSID}...")
        if wifi.connect():
            app_state = AppState.SyncTime
            # Give the "Syncing" message a frame on screen before the
            # blocking NTP request.
            next_sync_at = badge.ticks + 250

    elif app_state == AppState.SyncTime:
        message = "Syncing time..."
        if sync_attempts:
            message = f"Syncing time... (retry {sync_attempts})"
        draw_status(message)

        if badge.ticks >= next_sync_at:
            sync_attempts += 1
            if sync_time():
                app_state = AppState.Running
                # The radio isn't needed any more; save some battery
                wifi.disconnect()
            else:
                next_sync_at = badge.ticks + SYNC_RETRY_INTERVAL

    else:
        draw_countdown()


def on_exit():
    wifi.disconnect()


run(update)
