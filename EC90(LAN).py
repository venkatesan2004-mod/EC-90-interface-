# import socket
# import re

# # ASTM protocol control characters
# ENQ = b'\x05'
# ACK = b'\x06'
# STX = b'\x02'
# ETX = b'\x03'
# EOT = b'\x04'

# HOST = '0.0.0.0'
# PORT = 8000

# def parse_astm_frame(frame_text):
#     """Parses ASTM frame and extracts results from R| lines."""
#     lines = frame_text.strip().split('\r')
#     sample_id = None
#     results = []

#     for line in lines:
#         if line.startswith('P|'):
#             parts = line.split('|')
#             sample_id = parts[2] if len(parts) > 2 else 'UNKNOWN'

#         elif line.startswith('R|'):
#             parts = line.split('|')
#             if len(parts) >= 4:
#                 test_name = parts[2]  # e.g., GLU, UREA
#                 result_value = parts[3]
#                 results.append((test_name, result_value))

#     return sample_id, results

# def handle_astm_connection(conn):
#     buffer = b''

#     while True:
#         data = conn.recv(1024)
#         if not data:
#             break

#         if ENQ in data:
#             print("📥 [ENQ] Received — Sending ACK")
#             conn.sendall(ACK)

#         elif STX in data and ETX in data:
#             frame = data[data.find(STX)+1 : data.find(ETX)]  # Trim STX/ETX
#             try:
#                 text = frame.decode('ascii', errors='ignore')
#                 print("📥 Frame:\n", text.strip())

#                 # Parse results
#                 sample_id, results = parse_astm_frame(text)
#                 print(f"🧪 Sample ID: {sample_id}")
#                 for test, value in results:
#                     print(f"➡️ {test}: {value}")

#                 conn.sendall(ACK)
#             except Exception as e:
#                 print("❌ Decode error:", e)

#         elif EOT in data:
#             print("📴 [EOT] End of transmission")
#             break

#         else:
#             print("📥 Raw bytes:", data)
#             print("📥 Hex     :", data.hex())

#     conn.close()

# # Main server loop
# with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
#     s.bind((HOST, PORT))
#     s.listen(1)
#     print(f"🟢 Waiting for EC90 connection on port {PORT}...")

#     conn, addr = s.accept()
#     print(f"🔗 Connected from {addr}")
#     handle_astm_connection(conn)
import socket

# ASTM protocol control characters
ENQ = b'\x05'
ACK = b'\x06'
STX = b'\x02'
ETX = b'\x03'
EOT = b'\x04'

HOST = '0.0.0.0'
PORT = 8000

# Normal reference ranges
ref_ranges = {
    "Na": (135.0, 145.0),
    "K": (3.50, 5.10),
    "Cl": (98.0, 107.0),
}

# Full test names
test_names = {
    "Na": "Sodium",
    "K": "Potassium",
    "Cl": "Chloride",
}

def interpret_result(code, value):
    try:
        val = float(value)
        low, high = ref_ranges.get(code, (None, None))
        if low is not None and high is not None:
            if val < low:
                return f"{val} ⬇️ [Low]"
            elif val > high:
                return f"{val} ⬆️ [High]"
            else:
                return f"{val} ✅ [Normal]"
        return value
    except:
        return value

def parse_astm_frame(frame_text):
    lines = frame_text.strip().split('\r')
    sample_id = None
    results = []

    for line in lines:
        if line.startswith('P|'):
            parts = line.split('|')
            sample_id = parts[2] if len(parts) > 2 else 'UNKNOWN'

        elif line.startswith('R|'):
            parts = line.split('|')
            if len(parts) >= 4:
                raw_code = parts[2]
                test_code = raw_code.split('^')[-1]  # Extract Na from ^^Na
                result_value = parts[3]
                results.append((test_code, result_value))

    return sample_id, results

def handle_astm_connection(conn):
    while True:
        data = conn.recv(1024)
        if not data:
            break

        if ENQ in data:
            print("📥 [ENQ] Received — Sending ACK")
            conn.sendall(ACK)

        elif STX in data and ETX in data:
            frame = data[data.find(STX)+1 : data.find(ETX)]  # Trim STX/ETX
            try:
                text = frame.decode('ascii', errors='ignore')
                print("📥 Frame:\n", text.strip())

                sample_id, results = parse_astm_frame(text)
                print(f"\n🧪 Sample ID: {sample_id}")
                for code, value in results:
                    test_name = test_names.get(code, code)
                    formatted = interpret_result(code, value)
                    print(f"📊 {test_name:10}: {formatted}")
                print()
                conn.sendall(ACK)

            except Exception as e:
                print("❌ Decode error:", e)

        elif EOT in data:
            print("📴 [EOT] End of transmission")
            break

        else:
            print("📥 Raw bytes:", data)
            print("📥 Hex     :", data.hex())

    conn.close()

# Main server loop
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen(1)
    print(f"🟢 Waiting for EC90 connection on port {PORT}...")

    conn, addr = s.accept()
    print(f"🔗 Connected from {addr}")
    handle_astm_connection(conn)
