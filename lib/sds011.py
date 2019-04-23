from machine import  UART

ser = UART(1,baudrate=9600)
SDSisRunning = False

def readSDSvalues():
    global ser

    while True:
        n = ser.any()
        if n == 0:
            continue
        if n > 10:
            ser.read(n)
            continue
        rcv = ser.read(10)
        if len(rcv) != 10:
            continue
        if rcv[0] != 170 and rcv[1] != 192:
            print("try to sychronize")
            continue
        i = 0
        chksm = 0
        while i < 10:
            if i >= 2 and i <= 7:
                chksm = (chksm + rcv[i]) & 255
            i = i+1
        if chksm != rcv[8]:
            print("*** Checksum-Error")
            return -1,-1
        pm25 = (rcv[3]*256+rcv[2])
        pm10 = (rcv[5]*256+rcv[4])
        return pm10,pm25                    # values are in 0.1 resolution


def startstopSDS(state):
    global SDSisRunning, ser
    start_SDS_cmd = bytearray(b'\xAA\xB4\x06\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xFF\x06\xAB')
    stop_SDS_cmd =  bytearray(b'\xAA\xB4\x06\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xFF\x05\xAB')
    if state == True:
        ser.write(start_SDS_cmd)
        SDSisRunning = True
        print("SDS started.")
    else:
        ser.write(stop_SDS_cmd)
        SDSisRunning = False
        print("SDS stopped.")
# END def startstopSDS(was):
