import time
import math
import gc
from digitalio import DigitalInOut, Direction, Pull
import audioio
import audiocore
import audiomixer
import busio
import board
import neopixel
import adafruit_lis3dh
import random

# CUSTOMIZE YOUR COLOR HERE:
# (red, green, blue) -- each 0 (off) to 255 (brightest)
# COLOR = (255, 0, 0)  # red
# COLOR = (0, 255, 0)  # green
# COLOR = (0, 0, 255)  # blue
COLOR = (128, 0, 239)  # purple
# COLOR = (255, 255, 255)  # white
# COLOR = (0, 100, 255) #cyan

# CUSTOMIZE SENSITIVITY HERE: smaller numbers = more sensitive to motion
HIT_THRESHOLD = 700  # 250
SWING_THRESHOLD = 125

NUM_PIXELS = 160
# NUM_PIXELS = 85
NEOPIXEL_PIN = board.D5
POWER_PIN = board.D10
SWITCH_PIN = board.D9

enable = DigitalInOut(POWER_PIN)
enable.direction = Direction.OUTPUT
enable.value = False

red_led = DigitalInOut(board.D11)
red_led.direction = Direction.OUTPUT
green_led = DigitalInOut(board.D12)
green_led.direction = Direction.OUTPUT
blue_led = DigitalInOut(board.D13)
blue_led.direction = Direction.OUTPUT

audio = audioio.AudioOut(board.A0)  # Speaker
mode = 0  # Initial mode = OFF

strip = neopixel.NeoPixel(NEOPIXEL_PIN, NUM_PIXELS, brightness=1.0, auto_write=False)
strip.fill(0)  # NeoPixels off ASAP on startup
strip.show()

switch = DigitalInOut(SWITCH_PIN)
switch.direction = Direction.INPUT
switch.pull = Pull.UP

time.sleep(0.1)

# Set up accelerometer on I2C bus, 4G range:
i2c = busio.I2C(board.SCL, board.SDA)
accel = adafruit_lis3dh.LIS3DH_I2C(i2c)
accel.range = adafruit_lis3dh.RANGE_4_G

# "Idle" color is 1/4 brightness, "swinging" color is full brightness...
COLOR_IDLE = (int(COLOR[0] / 1), int(COLOR[1] / 1), int(COLOR[2] / 1))
COLOR_SWING = COLOR
COLOR_HIT = (255, 255, 255)  # "hit" color is white
COLOR_ACTIVE = COLOR_IDLE

TRIGGER_TIME = 0.0

VOLUME = 0.05

on_sounds = [
    audiocore.WaveFile(open('sounds/on0.wav', 'rb'))
]

off_sounds = [
    audiocore.WaveFile(open('sounds/off0.wav', 'rb'))
]

idle_sounds = [
    audiocore.WaveFile(open('sounds/idle1.wav', 'rb'))
]

swing_sounds = [
    audiocore.WaveFile(open('sounds/swing0.wav', 'rb')),
    audiocore.WaveFile(open('sounds/swing1.wav', 'rb')),
    audiocore.WaveFile(open('sounds/swing2.wav', 'rb')),
    audiocore.WaveFile(open('sounds/swing3.wav', 'rb')),
    audiocore.WaveFile(open('sounds/swing4.wav', 'rb')),
    audiocore.WaveFile(open('sounds/swing5.wav', 'rb')),
    audiocore.WaveFile(open('sounds/swing6.wav', 'rb')),
    audiocore.WaveFile(open('sounds/swing7.wav', 'rb')),
]

hit_sounds = [
    audiocore.WaveFile(open('sounds/hit0.wav', 'rb')),
    audiocore.WaveFile(open('sounds/hit1.wav', 'rb')),
    audiocore.WaveFile(open('sounds/hit2.wav', 'rb')),
    audiocore.WaveFile(open('sounds/hit3.wav', 'rb')),
    audiocore.WaveFile(open('sounds/hit4.wav', 'rb')),
]

mixer = audiomixer.Mixer(voice_count=2, sample_rate=22050, channel_count=1, bits_per_sample=16, samples_signed=True)
audio.play(mixer)


def play_track(voice, sounds, volume=1.0, loop=False):
    mixer.voice[voice].play(random.choice(sounds), loop=loop)
    mixer.voice[voice].level = volume * VOLUME


def power(sound, duration, reverse):
    if reverse:
        prev = NUM_PIXELS
    else:
        prev = 0
    gc.collect()  # Tidy up RAM now so animation's smoother
    start_time = time.monotonic()  # Save audio start time

    if sound == 'on':
        play_track(0, on_sounds)
    elif sound == 'off':
        play_track(0, off_sounds)

    while True:
        elapsed = time.monotonic() - start_time  # Time spent playing sound
        if elapsed > duration:  # Past sound duration?
            break  # Stop animating
        fraction = elapsed / duration  # Animation time, 0.0 to 1.0
        if reverse:
            fraction = 1.0 - fraction  # 1.0 to 0.0 if reverse
        fraction = math.pow(fraction, 0.5)  # Apply nonlinear curve
        threshold = int(NUM_PIXELS * fraction + 0.5)
        num = threshold - prev  # Number of pixels to light on this pass
        if num != 0:
            if reverse:
                strip[threshold:prev] = [0] * -num
            else:
                strip[prev:threshold] = [COLOR_IDLE] * num
            strip.show()
            # NeoPixel writes throw off time.monotonic() ever so slightly
            # because interrupts are disabled during the transfer.
            # We can compensate somewhat by adjusting the start time
            # back by 30 microseconds per pixel.
            start_time -= NUM_PIXELS * 0.00003
            prev = threshold

    if reverse:
        strip.fill(0)  # At end, ensure strip is off
    else:
        strip.fill(COLOR_IDLE)  # or all pixels set on
    strip.show()

    while mixer.voice[0].playing:  # Wait until audio done
        pass


def mix(color_1, color_2, weight_2):
    """
    Blend between two colors with a given ratio.
    @param color_1:  first color, as an (r,g,b) tuple
    @param color_2:  second color, as an (r,g,b) tuple
    @param weight_2: Blend weight (ratio) of second color, 0.0 to 1.0
    @return: (r,g,b) tuple, blended color
    """
    if weight_2 < 0.0:
        weight_2 = 0.0
    elif weight_2 > 1.0:
        weight_2 = 1.0
    weight_1 = 1.0 - weight_2
    return (int(color_1[0] * weight_1 + color_2[0] * weight_2),
            int(color_1[1] * weight_1 + color_2[1] * weight_2),
            int(color_1[2] * weight_1 + color_2[2] * weight_2))


# Main program loop, repeats indefinitely
while True:
    red_led.value = True

    if not switch.value:  # button pressed?
        if mode == 0:  # If currently off...
            enable.value = True
            blue_led.value = True
            power('on', 1.75, False)  # Power up!
            play_track(0, idle_sounds, loop=True)
            mode = 1  # ON (idle) mode now
        else:  # else is currently on...
            blue_led.value = False
            power('off', 1.15, True)  # Power down
            mode = 0  # OFF mode now
            enable.value = False
        while not switch.value:  # Wait for button release
            time.sleep(0.2)  # to avoid repeated triggering

    elif mode >= 1:  # If not OFF mode...
        x, y, z = accel.acceleration  # Read accelerometer
        accel_total = x * x + z * z
        # (Y axis isn't needed for this, assuming Hallowing is mounted
        # sideways to stick.  Also, square root isn't needed, since we're
        # just comparing thresholds...use squared values instead, save math.)
        if accel_total > HIT_THRESHOLD:  # Large acceleration = HIT
            TRIGGER_TIME = time.monotonic()  # Save initial time of hit
            play_track(1, hit_sounds)
            COLOR_ACTIVE = COLOR_HIT  # Set color to fade from
            mode = 3  # HIT mode
        elif accel_total > SWING_THRESHOLD:  # Mild = SWING
            TRIGGER_TIME = time.monotonic()  # Save initial time of swing
            play_track(1, swing_sounds)
            COLOR_ACTIVE = COLOR_SWING  # Set color to fade from
            mode = 2  # SWING mode

        if mode > 1:  # If in SWING or HIT mode...
            if mixer.voice[1].playing:  # And sound currently playing...
                blend = time.monotonic() - TRIGGER_TIME  # Time since triggered
                if mode == 2:  # If SWING,
                    blend = abs(0.5 - blend) * 2.0  # ramp up, down
                strip.fill(mix(COLOR_ACTIVE, COLOR_IDLE, blend))
                strip.show()
            else:  # No sound now, but still MODE > 1
                strip.fill(COLOR_IDLE)  # Set to idle color
                strip.show()
                mode = 1  # IDLE mode now