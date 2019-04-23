from network import LoRa
import socket
import machine
import time
import binascii
import sds011
from dth import DTH
import pycom
from ustruct import pack



class LoRaNetwork:
    def __init__(self):
        self.LORA_TX_POWER = 14
        self.LORA_RAW_FREQUENCY = 869500000
        self.LORA_RAW_SF = 12

        # LORAWAN_SF = 10
        self.LORAWAN_SF = 2

        self.lora = LoRa(mode=LoRa.LORA,region=LoRa.EU868, tx_power=self.LORA_TX_POWER, frequency=self.LORA_RAW_FREQUENCY, sf=self.LORA_RAW_SF)
        print("MacAddress: ",[hex(x) for x in self.lora.mac()])

        # create a trigger socket
        self.trigger_socket  = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
        # create a LoRa socket
        self.loraSocket = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
        self.loraSocket.setsockopt(socket.SOL_LORA, socket.SO_DR, self.LORAWAN_SF)


    def joinNetwork(self):
        app_eui = binascii.unhexlify('e5 e0 55 68 56 80 43 24'.replace(' ',''))
        app_key = binascii.unhexlify('a3 51 5e 56 2a 69 1e ea 50 f5 4e 18 d0 6c 54 a4'.replace(' ',''))
        print('joining...')
        # change join patameter
        self.lora.sf(12)
        self.lora.join(activation=LoRa.OTAA, auth=(app_eui, app_key), timeout=0,dr=0)
        while not self.lora.has_joined():
            time.sleep(5)
        print('joined')
        self.lora.nvram_save()

    def change_rawMode(self):
        self.lora.init(mode=LoRa.LORA,region=LoRa.EU868, tx_power=self.LORA_TX_POWER, frequency=self.LORA_RAW_FREQUENCY, sf=self.LORA_RAW_SF)

    def change_lorawanMode(self):
        self.lora.init(mode=LoRa.LORAWAN,region=LoRa.EU868)
        if not self.lora.has_joined():
            self.lora.nvram_restore()
            if not self.lora.has_joined():
                self.joinNetwork()

    #LoRaRAW
    def listening(self):
        socket = self.trigger_socket
        socket.setblocking(False)
        data = socket.recv(64)
        return data

    #LoRaWAN
    def send(self,sendBytes):
        try:
            self.loraSocket.send(sendBytes)
            self.lora.nvram_save()
            print('send finish')
            return True
        except:
            print('send error')
            return False

    '''
    def send(self,sendBytes):
        self.loraSocket.send(sendBytes)
        self.lora.nvram_save()
        print('send finish')
        return True
    '''

class Sensors:
    def __init__(self):
        # init DTH sensor
        self.th = DTH('P8',1)

    def read_dth(self):
        result = self.th.read()
        print(result.is_valid())
        if result.is_valid():
            DTH_temp = result.temperature
            DTH_humi = result.humidity
            return DTH_temp,DTH_humi

    def read_mass(self):
        if sds011.SDSisRunning != True:
            sds011.startstopSDS(True)
        time.sleep(20)
        pm_10,pm_25 = sds011.readSDSvalues()
        sds011.startstopSDS(False)
        if pm_10 + pm_25 != -2:
            pm10 = pm_10
            pm25 = pm_25
            #print(pm10/10.0)
            #print(pm25/10.0)
            sensor_error = 0
        else:
            pm10 = 0
            pm25 = 0
            sensor_error = 1
        time.sleep(2)
        result = self.th.read()
        if result.is_valid():
            DTH_temp = result.temperature
            DTH_humi = result.humidity
            #print(DTH_temp)
            #print(DTH_humi)
        else:
            sensor_error += result.error_code << 1
        # send data
        value = pm10,pm25,DTH_temp,DTH_humi
        #packet = pack('HHHH',pm10,pm25,(DTH_temp+2732),DTH_humi)
        #packet = pack('HHHH',pm10,pm25,DTH_temp,DTH_humi)
        return value



class AirApp:
    def __init__(self):
        self.appNum = 0x01
        self.devNum = 0x38
        self.stateNum_BoomDown = 0x01
        self.stateNum_BoomUp = 0x00
        self.isOverTime = False
        self.isBoomDown = False

        # setting for sample times
        self.samplingInterval = 60*100 #unit 10 ms 60s*100  = 1min
        self.groupSize_Boom_Down = 3 #times
        self.groupSize_Boom_Up = 15 # times

        self.lora = LoRaNetwork()
        self.sensors = Sensors()
        self.sendPacket = b''
        self.samplingCount = 0
        self.samplingBuf=[]

        self.sensors = Sensors()

        pycom.heartbeat(False)

    def LED_Red(self):
        pycom.rgbled(0xff0000)

    def LED_Green(self):
        pycom.rgbled(0x00ff00)

    def sendBuf(self,average):
        packet = b''
        # push packet
        if average == False:
            for i in self.samplingBuf:
                pm10,pm25,DTH_temp,DTH_humi = i
                packet += pack('HHHH',pm10,pm25,DTH_temp,DTH_humi)
        else:
            pm10 = 0
            pm25 = 0
            DTH_temp = 0
            DTH_humi = 0
            for i in self.samplingBuf:
                pm10_new,pm25_new,DTH_temp_new,DTH_humi_new = i
                pm10 = int((pm10+pm10_new)/2)
                pm25 = int((pm25+pm25_new)/2)
                DTH_temp = int((DTH_temp+DTH_temp_new)/2)
                DTH_humi = int((DTH_humi+DTH_humi_new)/2)
            # empty
            if pm10 != 0:
                packet = pack('HHHH',pm10,pm25,DTH_temp,DTH_humi)
        # send packet
        if packet != b'':
            self.loRaSend(packet)
        # clean buf
        self.samplingBuf.clear()

    def loRaSend(self,packet):
        self.lora.change_lorawanMode()
        while not self.lora.send(packet):
            print("EMS sleep")
            time.sleep(samplingInterval)
        self.lora.change_rawMode()
    # callback when receive boomDown (no blocking!)
    def boomDown(self):
        #print("boomDown")
        self.LED_Red()
        # send packet
        self.sendBuf(average = True)


    # callback when receive stop_pkg (no blocking!)
    def boomUp(self):
        #print("boomUp")
        self.LED_Green()
        # send packet
        self.sendBuf(average = False)

    # callback when sensors need sampling (no blocking!)
    def sampling(self):

        # sampling code
        self.samplingCount += 1
        # samping...
        sensors_result = self.sensors.read_mass()
        #push value to buf
        self.samplingBuf.append(sensors_result)

        # send group data
        if self.isBoomDown is True:
            if self.samplingCount == self.groupSize_Boom_Down:
                # clear counter
                self.samplingCount = 0
                # send buf
                self.sendBuf(average=False)

        # doing
        else:
            if self.samplingCount == self.groupSize_Boom_Up:
                self.samplingCount = 0
                # doing
                self.sendBuf(average=True)




        # fill send packet
        #self.sendPacket = b'finish'




    # callback when sampling (no blocking!)
    def overTime(self):
        print("overtime!")
        #self.sendPacket = b'overtime'
        #self.loRaSend()


    def running(self):
        pycom.rgbled(0x000000)
        self.lora.change_rawMode()
        isFastSampling = 0 #0:off 1:on
        sampling_timeStamp = 0
        while True:
            # state init is stop
            data = self.lora.listening()
            if data != b'':
                #print(data)
                recv_appNum = data[0]
                recv_devNum = data[1]
                recv_stateNum = data[2]

                if self.appNum == recv_appNum:
                    if self.devNum == recv_devNum:
                        if self.stateNum_BoomDown == recv_stateNum:
                            self.isBoomDown = True
                            self.boomDown()
                        elif self.stateNum_BoomUp == recv_stateNum:
                            self.isBoomDown = False
                            self.boomUp()

            # enter sampling
            if self.samplingInterval == sampling_timeStamp:
                sampling_timeStamp = 0
                self.sampling()

            time.sleep(0.01)
            sampling_timeStamp += 1


def main():
    app = AirApp()
    app.running()


if __name__ == '__main__':
    main()
