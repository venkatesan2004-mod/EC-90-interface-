import socket
import logging
import mysql.connector

# ------------------ Logging Setup ------------------
logging.basicConfig(
    filename="ec90_tcp_log.txt",
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    encoding="utf-8"
)
log = logging.getLogger()

# ------------------ ASTM Control Characters ------------------
ENQ = b'\x05'
ACK = b'\x06'
STX = b'\x02'
ETX = b'\x03'
EOT = b'\x04'

# ------------------ Network Config ------------------
HOST = '0.0.0.0'
PORT = 8000

# ------------------ Checksum Function ------------------
def calculate_checksum(data: bytes):
    total = sum(data + ETX)
    return f"{total & 0xFF:02X}"

# ------------------ Parse Records ------------------
def parse_records(lines):
    sample_id = None
    results = {}

    for line in lines:
        parts = line.split('|')
        if line.startswith('P|') and len(parts) > 2:
            sample_id = parts[2]
        elif line.startswith('R|') and len(parts) > 4:
            sample_id = parts[3]
        elif line.startswith('X|') and len(parts) > 6:
            code = parts[4].strip()
            value = parts[5].strip()
            results[code] = value

    return sample_id, results

# ------------------ Process Frames ------------------
def process_buffer(buffered_lines):
    records = []
    for raw_line in buffered_lines:
        if not (raw_line.startswith(STX) and ETX in raw_line):
            continue

        stx = raw_line.find(STX) + 1
        etx = raw_line.find(ETX)
        frame_data = raw_line[stx:etx]
        recv_cksum = raw_line[etx+1:etx+3].decode(errors='ignore').upper()
        calc_cksum = calculate_checksum(frame_data)

        if recv_cksum != calc_cksum:
            log.warning(f"❌ Checksum mismatch: got {recv_cksum}, expected {calc_cksum}")
            continue

        decoded = frame_data.decode(errors='ignore').strip()

        if '|' in decoded:
            parts = decoded.split('|', 1)
            if parts[0][-1].isalpha():
                decoded = parts[0][-1] + '|' + parts[1]
            else:
                decoded = parts[1]

        log.info(f"📄 Raw Frame: {decoded}")
        with open("frames.txt", "a", encoding="utf-8") as f:
            f.write(decoded + "\n")

        records.append(decoded)

    return records

# ------------------ MySQL Insert ------------------
def insert_to_mysql(sample_id, results):
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

        for test in ['Na', 'K', 'Cl']:
            value = results.get(test)
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
                log.info(f"✅ DB Insert: {sample_id} - {test} = {value}")
                next_id += 1

        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"❌ MySQL Error: {e}")

# ------------------ TCP Data Handler ------------------
def handle_tcp_connection(conn):
    print("📡 Connected")
    log.info("📡 Connected")
    temp_frame = b''
    buffered_lines = []
    receiving = False

    while True:
        data = conn.recv(1024)
        if not data:
            break

        if ENQ in data:
            print("🔔 ENQ received — sending ACK")
            log.info("🔔 ENQ received — sending ACK")
            conn.sendall(ACK)
            buffered_lines = []
            receiving = True
            continue

        if EOT in data:
            print("✅ EOT received — processing data")
            log.info("✅ EOT received — processing data")
            records = process_buffer(buffered_lines)
            sample_id, results = parse_records(records)

            print(f"\n🧾 Sample ID: {sample_id}")
            log.info(f"🧾 Sample ID: {sample_id}")

            for test in ['Na', 'K', 'Cl']:
                value = results.get(test)
                print(f"🧪 {test}: {value if value else '❌ Not found'}")
                log.info(f"🧪 {test}: {value if value else '❌ Not found'}")

            if sample_id:
                insert_to_mysql(sample_id, results)

            conn.sendall(ACK)
            receiving = False
            break

        if receiving:
            temp_frame += data
            while b'\n' in temp_frame:
                line, temp_frame = temp_frame.split(b'\n', 1)
                buffered_lines.append(line.strip())
                conn.sendall(ACK)

    conn.close()
    print("🔌 TCP connection closed")
    log.info("🔌 TCP connection closed\n")

# ------------------ TCP Server Main ------------------
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen(1)
    print(f"🟢 Listening for EC90 on port {PORT}...")
    log.info(f"🟢 Listening for EC90 on port {PORT}...")

    while True:
        conn, addr = s.accept()
        print(f"🔗 Connected from {addr}")
        log.info(f"🔗 Connected from {addr}")
        handle_tcp_connection(conn)
