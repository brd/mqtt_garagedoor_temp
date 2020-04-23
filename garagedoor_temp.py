#!/usr/bin/env python3

import paho.mqtt.client as mqtt
import time
import subprocess

# Which GPIO pins
garagedoor = {
  'state_pin': 17,
  'toggle_pin': 18,
  'status': 3,
  'mqtt_target': 'house/door/garage_target',
  'mqtt_pub': 'house/door/garage'
}


def on_connect(client, userdata, flags, rc):
  print('Connected with result code '+str(rc))
  client.subscribe(garagedoor['mqtt_target'], 2)


def on_message(client, userdata, msg):
  print(msg.topic + ' ' + msg.payload.decode("utf-8"))
  if msg.topic == 'house/door/garage_target':
    if garagedoor["status"] == 1 and msg.payload.decode("utf-8") == "Open":
      print(f'calling trigger_door')
      trigger_door()
    if garagedoor['status'] == 0 and msg.payload.decode("utf-8") == "Closed":
      trigger_door()


def trigger_door():
  print(f'==> trigger_door()')
  gpio = subprocess.run(['gpioctl', str(garagedoor['toggle_pin']), "1"], capture_output=True, text=True)
  if gpio.returncode != 0:
    print(f'error calling gpioctl: {gpioctl.stdout} {gpioctl.stderr}')
  time.sleep(1)
  gpio = subprocess.run(['gpioctl', str(garagedoor['toggle_pin']), "0"], capture_output=True, text=True)
  if gpio.returncode != 0:
    print(f'error calling gpioctl: {gpioctl.stdout} {gpioctl.stderr}')


def read_temp():
  # sysctls: dev.gpioths.0.fails, dev.gpioths.0.humidity, dev.gpioths.0.temperature
  fails = subprocess.run(['sysctl', '-n', 'dev.gpioths.0.fails'], capture_output=True, text=True)
  if fails.stdout.rstrip() == "0":
    ht = { }
    ht['h'] = subprocess.run(['sysctl', '-n', 'dev.gpioths.0.humidity'], capture_output=True, text=True).stdout.rstrip()
    ht['t'] = subprocess.run(['sysctl', '-n', 'dev.gpioths.0.temperature'], capture_output=True, text=True).stdout.rstrip()
    return ht
  return None


def main():
  next_temp_read = time.time()
  next_garage_read = time.time()

  # Setup MQTT
  client = mqtt.Client()
  client.will_set('house/status/garage', 'false')
  client.on_connect = on_connect
  client.on_message = on_message
  client.connect('192.168.1.31')
  client.loop_start()

  # send active message
  client.publish('house/status/garage', 'true')

  while True:
    # Publish temp
    if time.time() > next_temp_read:
      ht = read_temp()
      if ht != None:
        print(f'publish: temp: {ht["t"]}; humidity: {ht["h"]}')
        client.publish('house/garage/temperature', ht['t'])
        client.publish('house/garage/humidity', ht['h'])
        next_temp_read += 60

    # Check garage door
    if time.time() > next_garage_read:
      gd = subprocess.run(['gpioctl', str(garagedoor['state_pin'])], capture_output=True, text=True)
      print(f'check garage door: status: {garagedoor["status"]}; state: {gd.stdout.rstrip()}')
      # 1 = closed
      if gd.stdout.rstrip() == "1" and garagedoor['status'] == 0:
        print(f'garagedoor: 1 and 0')
        garagedoor['status'] = 1
        client.publish(garagedoor['mqtt_pub'], 'Closed')
      elif gd.stdout.rstrip() == "0" and garagedoor['status'] == 1:
        print(f'garagedoor: 0 and 1')
        garagedoor['status'] = 0
        client.publish(garagedoor['mqtt_pub'], 'Open')
      else:
        if gd.stdout.rstrip() == "0":
          garagedoor['status'] = 0
          client.publish(garagedoor['mqtt_pub'], 'Open')
        if gd.stdout.rstrip() == "1":
          garagedoor['status'] = 1
          client.publish(garagedoor['mqtt_pub'], 'Closed')

      next_garage_read += 5


if __name__ == '__main__':
  main()
