import serial
import time
import threading
import atexit
import sys
import wave
from datetime import datetime

class Modem:
    def __init__(self):
        self.analog_modem = serial.Serial()
        self.analog_modem.port = "/dev/ttyACM0"
        self.analog_modem.baudrate = 57600
        self.analog_modem.bytesize = serial.EIGHTBITS
        self.analog_modem.parity = serial.PARITY_NONE
        self.analog_modem.stopbits = serial.STOPBITS_ONE
        self.analog_modem.timeout = 3
        self.analog_modem.xonxoff = False
        self.analog_modem.rtscts = False
        self.analog_modem.dsrdtr = False
        self.analog_modem.writeTimeout = 3

        self.disable_modem_event_listener = True
        self.RINGS_BEFORE_AUTO_ANSWER = 2
        self.audio_file_name = ''

    def init_modem_settings(self):
        try:
            self.analog_modem.open()
        except Exception as e:
            print(f"Error: Unable to open the Serial Port. {e}")
            sys.exit()

        try:
            self.analog_modem.flushInput()
            self.analog_modem.flushOutput()

            '''
            ATZ: default factory profile, any call will be terminated
            ATV1: Returns result codes in words (English)
            ATE1: Modem command echo enable
            AT+GCI=B4: sets country of installation, this is needed for caller ID to work
            AT+VCID=1: Enable caller ID
            '''
            commands = ["AT", "ATZ", "ATV1", "ATE1", "AT+GCI=B4", "AT+VCID=1"]
            for cmd in commands:
                if not self.exec_AT_cmd(cmd):
                    print(f"Error: Command {cmd} failed")
                    sys.exit()
        except Exception as e:
            print(f"Error: unable to Initialize the Modem. {e}")
            sys.exit()
        

    # Execute AT command
    def exec_AT_cmd(self, modem_AT_cmd):
        try:
            self.disable_modem_event_listener = True

            cmd = modem_AT_cmd + "\r"
            self.analog_modem.write(cmd.encode())

            modem_response = self.analog_modem.readline().decode() + self.analog_modem.readline().decode()

            print(modem_response)

            self.disable_modem_event_listener = False

            if ("OK" in modem_response) or (("CONNECT" in modem_response) and (modem_AT_cmd in ["AT+VTX", "AT+VRX"])):
                return True
            else:
                return False
        except Exception as e:
            print(f"Error: unable to write AT command to the modem... {e}")
            self.disable_modem_event_listener = False
            return False
        

    def play_audio(self):
        print("Play Audio Msg - Start")
        if not self.exec_AT_cmd("AT+FCLASS=8"):
            print("Error: Failed to put modem into voice mode.")
            return

        if not self.exec_AT_cmd("AT+VSM=128,8000"):
            print("Error: Failed to set compression method and sampling rate specifications.")
            return

        '''
        AT+VTX: begin transmitting audio data
        AT+VLS=1: switches modem out of speakerphone mode and into TAD mode 
        '''
        if not self.exec_AT_cmd("AT+VLS=1") or not self.exec_AT_cmd("AT+VTX"):
            print("Error: Unable put modem into TAD mode.")
            return

        time.sleep(1)
        self.disable_modem_event_listener = True

        with wave.open('message.wav', 'rb') as wf:
            chunk = 1024
            data = wf.readframes(chunk)
            while data:
                self.analog_modem.write(data)
                data = wf.readframes(chunk)
                time.sleep(.12)

        cmd = "<DLE><ETX>\r".encode() # indicates end of voice transmit data
        self.analog_modem.write(cmd)

        # Wait for modem to acknowledge or time out
        timeout = time.time() + 120  # 2 minutes
        while True:
            response = self.analog_modem.readline().decode()
            if "OK" in response or time.time() > timeout:
                break

        self.disable_modem_event_listener = False
        print("Play Audio Msg - End")
        # Do not hang up here, let the recording start next

        

    def play_audio_and_record(self):
        self.play_audio()  # Function to play audio remains unchanged

        # Start recording after playing audio
        print("Record Audio Msg - Start")
        if not self.exec_AT_cmd("AT+FCLASS=8"):
            print("Error: Failed to put modem into voice mode.")
            return

        # Set speaker volume to normal
        if not self.exec_AT_cmd("AT+VGT=128"):
            print("Error: Failed to set speaker volume to normal.")
            return

        # Compression Method and Sampling Rate Specifications
        if not self.exec_AT_cmd("AT+VSM=128,8000"):
            print("Error: Failed to set compression method and sampling rate specifications.")
            return

        # Disables silence detection (Value: 0)
        if not self.exec_AT_cmd("AT+VSD=128,0"):
            print( "Error: Failed to disable silence detection.")
            return
        
        # Put modem into TAD Mode
        if not self.exec_AT_cmd("AT+VLS=1"):
            print("Error: Unable put modem into TAD mode.")
            return

        # Enable silence detection.
        if not self.exec_AT_cmd("AT+VSD=128,50"):
            print("Error: Failed to enable silence detection.")
            return
        
        # Play beep.
        if not self.exec_AT_cmd("AT+VTS=[933,900,100]"):
            print("Error: Failed to play 1.2 second beep.")
            #return

        # Select voice receive mode
        if not self.exec_AT_cmd("AT+VRX"):
            print("Error: Unable put modem into voice receive mode.")
            return

        # Record Audio File
        start_time = datetime.now()
        CHUNK = 1024
        audio_frames = []

        while True:
            audio_data = self.analog_modem.read(CHUNK)
            print(repr(audio_data))  # debug
            # Check if <DLE>b is in the stream
            if (b"\x10b" in audio_data):
                print("Busy Tone... Call will be disconnected.")
                break

            # Check if <DLE><ETX> is in the stream
            ## TODO: figure out this issue
            if (b"\x10\x03" in audio_data):
                print("<DLE><ETX> Char Received... Call will be disconnected.")
                break

            # Timeout
            elif (datetime.now() - start_time).total_seconds() > 120:
                print("Timeout - Max recording limit reached.")
                break

            # Add Audio Data to Audio Buffer
            audio_frames.append(audio_data)

        # Save the Audio into a .wav file
        datetime_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.audio_file_name = f'recorded_message_{datetime_stamp}.wav'

        with wave.open(self.audio_file_name, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(1)
            wf.setframerate(8000)
            wf.writeframes(b''.join(audio_frames))

        # Hang up the call
        self.exec_AT_cmd("ATH")
        print("Record Audio Msg - END")

    def close_modem_port(self):
        if self.analog_modem.isOpen():
            self.exec_AT_cmd("ATH")
            self.analog_modem.close()
            print("Serial Port closed...")

    def read_data(self):
        ring_count = 0
        try:
            while True:
                if not self.disable_modem_event_listener:
                    modem_data = self.analog_modem.readline().decode().strip()
                    if modem_data:
                        print(modem_data)
                        if "RING" in modem_data:
                            ring_count += 1
                            if ring_count >= self.RINGS_BEFORE_AUTO_ANSWER:
                                ring_count = 0  # Reset ring count after answering
                                self.play_audio_and_record()
        except Exception as e:
            print(f"Error reading from modem: {e}")


modem = Modem()
modem.init_modem_settings()

# Start a new thread to listen to modem data
data_listener_thread = threading.Thread(target=modem.read_data)
data_listener_thread.start()

# Ensure the modem is closed properly upon program termination
atexit.register(modem.close_modem_port)

