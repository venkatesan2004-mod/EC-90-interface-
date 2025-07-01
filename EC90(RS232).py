import serial
import time

# Set your COM port and baudrate here
PORT = 'COM3'
BAUDRATE = 9600

ser = serial.Serial(PORT, BAUDRATE, timeout=1)
print(f"🔌 Listening on {PORT} @ {BAUDRATE} baud...")

buffer = ''
while True:
    try:
        line = ser.readline().decode('ascii', errors='ignore').strip()
        if line:
            print("📥", line)
            buffer += line + '\n'

        if 'L|' in line:
            print("✅ End of ASTM Message")
            break

    except KeyboardInterrupt:
        print("🔴 Interrupted")
        break

ser.close()
