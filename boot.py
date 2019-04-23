from machine import UART
import machine
import os
import pycom

uart = UART(0, baudrate=115200)
os.dupterm(uart)
pycom.wifi_on_boot(False)
machine.main('main.py')
