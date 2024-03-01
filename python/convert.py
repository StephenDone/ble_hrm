def ToHex(bytes):
    return f'[{" ".join(map("{:02x}".format, bytes))}]'

def unsigned_16(b1, b2):
    return b1 | b2 << 8

def minutes_seconds(s):
    minutes = int(s) // 60
    seconds = int(s) % 60
    return f'{minutes:02d}:{seconds:02d}'