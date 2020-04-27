#!/usr/bin/env python3

import paho.mqtt.client as mqtt
import sched
import subprocess
import time

# Which GPIO pins
config = {
  'mqtt_status': 'house/status/garage',
  'gd_read_interval': 3,
  'gd_state_pin': 17,
  'gd_toggle_pin': 18,
  'gd_status': 'unknown',
  'gd_mqtt_target': 'house/door/garage_target',
  'gd_mqtt_pub': 'house/door/garage',
  'temp_read_interval': 60,
  'temp_sysctl_fails': 'dev.gpioths.0.fails',
  'temp_sysctl_temperature': 'dev.gpioths.0.temperature',
  'temp_sysctl_humidity': 'dev.gpioths.0.humidity',
  'temp_mqtt_temperature': 'house/temperature/garage',
  'temp_mqtt_humidity': 'house/humidity/garage'
}


def on_connect(client, userdata, flags, rc):
  print('Connected with result code '+str(rc))
  client.subscribe(config['gd_mqtt_target'], 2)


def on_message(client, userdata, msg):
  print(msg.topic + ' ' + msg.payload.decode("utf-8"))
  if msg.topic == config['gd_mqtt_target']:
    if config['gd_status'] == 1 and msg.payload.decode("utf-8") == "Open":
      print(f'calling trigger_door')
      trigger_door()
    if config['gd_status'] == 0 and msg.payload.decode("utf-8") == "Closed":
      print(f'calling trigger_door')
      trigger_door()


def trigger_door():
  print(f'==> trigger_door()')
  gpio = subprocess.run(['gpioctl', str(config['gd_toggle_pin']), "1"], capture_output=True, text=True)
  if gpio.returncode != 0:
    print(f'error calling gpioctl: {gpioctl.stdout} {gpioctl.stderr}')
  time.sleep(1)
  gpio = subprocess.run(['gpioctl', str(config['gd_toggle_pin']), "0"], capture_output=True, text=True)
  if gpio.returncode != 0:
    print(f'error calling gpioctl: {gpioctl.stdout} {gpioctl.stderr}')


def read_temp(config):
  # sysctls: dev.gpioths.0.fails, dev.gpioths.0.humidity, dev.gpioths.0.temperature
  fails = subprocess.run(['sysctl', '-n', config['temp_sysctl_fails']], capture_output=True, text=True)
  if fails.stdout.rstrip() == "0":
    h = subprocess.run(['sysctl', '-n', config['temp_sysctl_humidity']], capture_output=True, text=True).stdout.rstrip()
    t = subprocess.run(['sysctl', '-n', config['temp_sysctl_temperature']], capture_output=True, text=True).stdout.rstrip().rstrip('C')
    print(f'publish: temp: {t}C; humidity: {h}')
    config['mqttc'].publish(config['temp_mqtt_temperature'], t)
    config['mqttc'].publish(config['temp_mqtt_humidity'], h)

  # Schedule next temp read
  config['s'].enter(config['temp_read_interval'], 1, read_temp, argument=(config,))


def check_garage_door(config):
  gd = subprocess.run(['gpioctl', str(config['gd_state_pin'])], capture_output=True, text=True)
  print(f'check garage door: status: {config["gd_status"]}; state: {gd.stdout.rstrip()}')
  # 1 = closed
  if gd.stdout.rstrip() == "1" and config['gd_status'] == 0:
    print(f'garagedoor: 1 and 0')
    config['gd_status'] = 1
    config['mqttc'].publish(config['gd_mqtt_pub'], 'Closed')
  elif gd.stdout.rstrip() == "0" and config['gd_status'] == 1:
    print(f'garagedoor: 0 and 1')
    config['gd_status'] = 0
    config['mqttc'].publish(config['gd_mqtt_pub'], 'Open')
  elif config['gd_status'] == 'unknown':
    if gd.stdout.rstrip() == "0":
      print(f'publish: door open')
      config['gd_status'] = 0
      config['mqttc'].publish(config['gd_mqtt_pub'], 'Open')
    if gd.stdout.rstrip() == "1":
      print(f'publish: door closed')
      config['gd_status'] = 1
      config['mqttc'].publish(config['gd_mqtt_pub'], 'Closed')

  # Schedule next garage door check
  config['s'].enter(config['gd_read_interval'], 2, check_garage_door, argument=(config,))


def main():

  # Setup MQTT
  config['mqttc'] = mqtt.Client()
  config['mqttc'].will_set(config['mqtt_status'], 'false')
  config['mqttc'].on_connect = on_connect
  config['mqttc'].on_message = on_message
  config['mqttc'].connect('192.168.1.31')
  config['mqttc'].loop_start()

  # Setup scheduler
  config['s'] = sched.scheduler()

  # send active message
  config['mqttc'].publish(config['mqtt_status'], 'true')

  # Schedule first temp check
  config['s'].enter(2, 1, read_temp, argument=(config,))

  # Schedule first garage door check
  config['s'].enter(config['gd_read_interval'], 2, check_garage_door, argument=(config,))

  # Run
  config['s'].run()

if __name__ == '__main__':
  main()
