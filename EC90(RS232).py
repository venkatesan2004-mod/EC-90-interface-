import serial
import logging
import mysql.connector

# ---------------------- LOG SETUP ----------------------
log = logging.getLogger()
log.setLevel(logging.INFO)

if log.hasHandlers():
    log.handlers.clear()

file_handler = logging.FileHandler("ec90_log.txt", mode='a', encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
log.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(message)s'))
log.addHandler(console_handler)

# ---------------------- SETTINGS ----------------------
PORT = 'COM5'
BAUDRATE = 115200

# ---------------------- CHECKSUM ----------------------
def calculate_checksum(frame_data: bytes):
    total = sum(frame_data + b'\x03')
    return f"{total & 0xFF:02X}"

# ---------------------- PARSE FRAMES ----------------------
def parse_ec90_records(lines):
    sample_id = None
    results = {'Na': None, 'K': None, 'Cl': None}

    for line in lines:
        fields = line.split('|')
        if line.startswith('R|') and len(fields) > 4:
            sample_id = fields[3]
        elif line.startswith('X|') and len(fields) > 6:
            test_name = fields[4].strip()
            test_value = fields[5].strip()
            if test_name in results:
                results[test_name] = test_value

    return sample_id, results

# ---------------------- WRITE TO DB ----------------------
def insert_results_to_mysql(sample_id, results):
    try:
        conn = mysql.connector.connect(
            host='192.168.20.160',
            user='remoteapi',
            password='kmc@123',
            database='kmc_05_06_2025_server'
        )
        cursor = conn.cursor()

        cursor.execute("SELECT MAX(LIS_ID) FROM lis_machineresult")
        max_id = cursor.fetchone()[0] or 0
        next_id = max_id + 1

        for test, value in results.items():
            if value:
                cursor.execute("""
                    INSERT INTO lis_machineresult (
                        LIS_ID, LIS_MACHNAME, LIS_MACHID, LIS_LABID,
                        LIS_MACHTESTID, LIS_MACHRESULTS, LIS_RPREVIEW
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    next_id, "ELECTROLYTE ANALYZER", "EC 90", sample_id,
                    test, value, 0
                ))
                log.info(f"✅ DB Inserted: {sample_id} | {test} = {value}")
                next_id += 1

        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"❌ DB Error: {e}")

# ---------------------- FRAME PROCESSOR ----------------------
def process_buffer(buffered_lines):
    records = []
    for raw_line in buffered_lines:
        if raw_line.startswith(b'\x02') and b'\x03' in raw_line:
            stx = raw_line.find(b'\x02') + 1
            etx = raw_line.find(b'\x03')
            frame_data = raw_line[stx:etx]
            recv_cksum = raw_line[etx + 1:etx + 3].decode(errors='ignore').upper()
            calc_cksum = calculate_checksum(frame_data)

            if recv_cksum != calc_cksum:
                log.warning(f"⚠️ Checksum mismatch: Got {recv_cksum}, Expected {calc_cksum}")
                continue

            decoded = frame_data.decode(errors='ignore').strip()

            # Clean frame number prefix
            if '|' in decoded:
                parts = decoded.split('|', 1)
                if parts[0][-1].isalpha():
                    decoded = parts[0][-1] + '|' + parts[1]
                else:
                    decoded = parts[1]

            # ✅ Write decoded line to frames.txt
            with open("frames.txt", "a", encoding="utf-8") as f:
                f.write(decoded + "\n")

            records.append(decoded)
    return records

# ---------------------- MAIN ----------------------
def main():
    log.info(f"📡 Listening on {PORT} @ {BAUDRATE} baud...")
    ser = serial.Serial(PORT, BAUDRATE, timeout=1)

    buffer = []
    temp = b''
    receiving = False

    while True:
        byte = ser.read()
        if not byte:
            continue

        if byte == b'\x05':  # ENQ
            log.info("🔔 ENQ received — sending ACK")
            ser.write(b'\x06')
            buffer = []
            receiving = True
            continue

        if byte == b'\x04':  # EOT
            log.info("✅ EOT received — parsing data...")
            records = process_buffer(buffer)
            sample_id, results = parse_ec90_records(records)

            log.info(f"🧾 Sample ID : {sample_id}")
            for test in ['Na', 'K', 'Cl']:
                log.info(f"🧪 {test}: {results[test]}")

            if sample_id:
                insert_results_to_mysql(sample_id, results)
            else:
                log.warning("⚠️ No valid sample ID found.")

            log.info("🔁 Ready for next sample\n")
            receiving = False
            continue

        if receiving:
            temp += byte
            if byte == b'\n':
                buffer.append(temp.strip())
                ser.write(b'\x06')  # ACK
                temp = b''

if __name__ == "__main__":
    main()
