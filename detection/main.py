import keys
import os
import notecard
from pathlib import Path
from periphery import I2C
import picamera
import RPi.GPIO as GPIO
from detection.run_tf_detector import load_and_run_detector
from run_tf_detector_batch import load_and_run_detector_batch, write_results_to_file
import time

# -------------------- CONFIG --------------------

notehub_uid = 'com.blues.tvantoll:pestcontrol'

TRIG_PIN = 11      # Ultrasonic Trigger
ECHO_PIN = 12      # Ultrasonic Echo
LED_PIN = 17       # LED

DISTANCE_THRESHOLD = 20  # cm (adjust for insect detection range)

# ------------------------------------------------

# Setup Notecard
port = I2C("/dev/i2c-1")
card = notecard.OpenI2C(port, 0, 0)

# Load model
model = ''.join([str(f) for f in Path('.').rglob('*.pb')])

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(TRIG_PIN, GPIO.OUT)
GPIO.setup(ECHO_PIN, GPIO.IN)
GPIO.setup(LED_PIN, GPIO.OUT)

GPIO.output(TRIG_PIN, False)
GPIO.output(LED_PIN, False)

time.sleep(2)

# -------------------- ULTRASONIC FUNCTION --------------------

def get_distance():
    GPIO.output(TRIG_PIN, True)
    time.sleep(0.00001)
    GPIO.output(TRIG_PIN, False)

    while GPIO.input(ECHO_PIN) == 0:
        pulse_start = time.time()

    while GPIO.input(ECHO_PIN) == 1:
        pulse_end = time.time()

    pulse_duration = pulse_end - pulse_start
    distance = pulse_duration * 17150
    return round(distance, 2)

# -------------------- ML PROCESSING --------------------

def process_image(file_name):
    output_path = './output.json'
    results = load_and_run_detector_batch(
        model_file=model,
        image_file_names=[file_name],
        checkpoint_path=output_path,
        confidence_threshold=0.6,
    )
    write_results_to_file(results, output_path)
    return results

def is_insect_image(ml_result):
    for detection in ml_result['detections']:
        if detection['category'] == '1':  # '1' = animal (use for insect)
            return True
    return False

# -------------------- CAMERA --------------------

def get_image_name():
    path, dirs, files = next(os.walk('images'))
    return 'images/' + str(len(files) + 1) + '.jpg'

def take_picture():
    camera = picamera.PiCamera()
    camera.resolution = (400, 400)
    time.sleep(2)
    camera.rotation = 90
    image_name = get_image_name()
    camera.capture(image_name)
    camera.close()
    return image_name

# -------------------- NOTECARD --------------------

def init_notecard():
    req = {"req": "hub.set"}
    req["product"] = notehub_uid
    req["mode"] = "continuous"
    req["sync"] = True
    card.Transaction(req)

def send_to_notehub():
    req = {"req": "note.add"}
    req["file"] = "twilio.qo"
    req["sync"] = True
    req["body"] = {
        "body": "Insect detected!",
        "from": keys.sms_from,
        "to": keys.sms_to,
    }
    card.Transaction(req)

# -------------------- MAIN LOOP --------------------

def main():
    init_notecard()

    while True:
        distance = get_distance()
        print("Distance:", distance, "cm")

        if distance < DISTANCE_THRESHOLD:
            print("Object detected by Ultrasonic Sensor")
            GPIO.output(LED_PIN, True)

            image_name = take_picture()
            ml_result = process_image(image_name)[0]

            if is_insect_image(ml_result):
                print("Insect detected!")
                send_to_notehub()
            else:
                print("No insect detected")
                os.remove(image_name)

            GPIO.output(LED_PIN, False)
            time.sleep(5)

        time.sleep(1)

try:
    main()
except KeyboardInterrupt:
    print("Program stopped")
    GPIO.cleanup()