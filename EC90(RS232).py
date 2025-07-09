import serial

# ---------------------- SETTINGS ----------------------
PORT = 'COM5'           # ⚠️ Change this to your actual COM port
BAUDRATE = 115200       # EC90 default
# -------------------------------------------------------

def calculate_checksum(frame_data: bytes):
    """
    ASTM checksum calculation:
    Sum all bytes between STX and ETX (ETX INCLUDED), then take lowest 8 bits (mod 256).
    Return 2-digit uppercase hex string.
    """
    total = sum(frame_data + b'\x03')  # Include ETX
    return f"{total & 0xFF:02X}"

def parse_astm_records(lines):
    """
    Parse ASTM records like P| (patient), OBX| (results).
    """
    data = {
        'sample_id': None,
        'patient_name': None,
        'results': {}
    }

    for line in lines:
        if line.startswith('P|'):
            fields = line.split('|')
            if len(fields) > 2:
                data['sample_id'] = fields[2]
            if len(fields) > 4:
                data['patient_name'] = fields[4].replace('^', ' ')
        elif line.startswith('OBX|'):
            fields = line.split('|')
            if len(fields) > 5:
                test_name = fields[4].strip()
                test_value = fields[5].strip()
                unit = fields[6].strip() if len(fields) > 6 else ''
                data['results'][test_name] = (test_value, unit)
    return data

def process_buffer(buffered_lines):
    """
    Validate checksum and extract text from ASTM frames.
    """
    records = []
    for raw_line in buffered_lines:
        if raw_line.startswith(b'\x02') and b'\x03' in raw_line:
            stx_index = raw_line.find(b'\x02') + 1
            etx_index = raw_line.find(b'\x03')
            frame_data = raw_line[stx_index:etx_index]
            recv_checksum = raw_line[etx_index + 1:etx_index + 3].decode(errors='ignore').upper()
            calc_checksum = calculate_checksum(frame_data)
            if calc_checksum != recv_checksum:
                print(f"❌ Checksum mismatch! Got {recv_checksum}, expected {calc_checksum}")
                continue
            decoded_line = frame_data.decode(errors='ignore').strip()
            print(f"📄 Raw Frame: {decoded_line}")  # ✅ DEBUG line
            records.append(decoded_line)
    return records

def main():
    print(f"📡 Listening on {PORT} @ {BAUDRATE} baud...")
    ser = serial.Serial(PORT, BAUDRATE, timeout=1)

    temp_frame = b''
    buffered_lines = []
    receiving = False

    while True:
        byte = ser.read()
        if not byte:
            continue

        # --- ENQ received ---
        if byte == b'\x05':
            print("🔔 ENQ received — sending ACK")
            ser.write(b'\x06')  # ACK
            buffered_lines = []
            receiving = True
            continue

        # --- EOT received ---
        if byte == b'\x04':
            print("✅ EOT received — end of transmission")
            records = process_buffer(buffered_lines)
            parsed = parse_astm_records(records)

            print("\n📋 Parsed Result:")
            print(f"🧾 Sample ID : {parsed['sample_id']}")
            print(f"👤 Patient   : {parsed['patient_name']}")
            if parsed['results']:
                for test, (value, unit) in parsed['results'].items():
                    print(f"🧪 {test}: {value} {unit}")
            else:
                print("⚠️ No test results found.")
            print("✅ Listening for next sample...\n")

            receiving = False
            continue

        # --- Collecting frame ---
        if receiving:
            temp_frame += byte
            if byte == b'\n':  # LF ends each frame
                buffered_lines.append(temp_frame.strip())
                ser.write(b'\x06')  # ACK each frame
                temp_frame = b''

if __name__ == "__main__":
    main()
