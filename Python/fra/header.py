from .common import methods
import struct
from .tools.headb import headb

b3_to_bits = {
    0b110: 512,
    0b101: 256,
    0b100: 128,
    0b011: 64,
    0b010: 32,
    0b001: 16
}

class header:
    def parse(file_path):
        d = list()
        with open(file_path, 'rb') as f:
            header = f.read(256)

            methods.signature(header[0x0:0xa])
            headlen = struct.unpack('<Q', header[0xa:0x12])[0]
            blocks = f.read(headlen - 256)
            i = j = 0
            image = b''
            while i < len(blocks):
                block_type = blocks[i:i+2]
                if block_type == b'\xfa\xaa':
                    block_length = int.from_bytes(blocks[i+2:i+8], 'little')
                    title_length = int(struct.unpack('<I', blocks[i+8:i+12])[0])
                    title = blocks[i+12:i+12+title_length].decode('utf-8')
                    data = blocks[i+12+title_length:i+block_length]
                    d.append([title, data])
                    i += block_length; j += 1
                elif block_type == b'\xf5\x55':
                    block_length = int(struct.unpack('<Q', blocks[i+2:i+10])[0])
                    data = blocks[i+10:i+block_length]
                    image = data
                    i += block_length
        return d, image

    def modify(file_path, meta = None, img: bytes = None):
        with open(file_path, 'rb') as f:
                head = f.read(256)

                header_length = struct.unpack('<Q', head[0xa:0x12])[0]
                sample_rate = head[0x12:0x15]
                cfb = struct.unpack('<B', head[0x15:0x16])[0]
                is_ecc_on = True if (struct.unpack('<B', head[0x16:0x17])[0] >> 7) == 0b1 else False
                checksum_header = head[0xf0:0x100]

                channel = (cfb >> 3) + 1
                bits = b3_to_bits.get(cfb & 0b111)

                f.seek(header_length)
                audio = f.read()

                head_new = headb.uilder(sample_rate, channel, bits, is_ecc_on, checksum_header,
                meta, img)

        with open(file_path, 'wb') as f:
                f.write(head_new)
                f.write(audio)
