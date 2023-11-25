import hashlib
from ml_dtypes import bfloat16
import numpy as np
import os
from scipy.fft import ifft
import struct
import subprocess
from .tools.ecc import ecc

class decode:
    def mono(data, bits):
        data = data[:,0] * np.exp(1j * data[:,1])
        wave = np.int32(np.real(ifft(data)))

        if bits == 32: pass
        elif bits == 16: wave = np.int16(wave / 2**16)
        elif bits == 8: wave = np.uint8(wave / 2**24 + 2**7)
        else: raise ValueError(f"Illegal value {bits} for bits: only 8, 16, and 32 bits are available for decoding.")

        return wave

    def stereo(data, bits):
        left_freq = data[:, 0] * np.exp(1j * data[:, 1])
        right_freq = data[:, 2] * np.exp(1j * data[:, 3])

        left_wave = np.int32(np.fft.ifft(left_freq).real)
        right_wave = np.int32(np.fft.ifft(right_freq).real)
        if bits == 32:
            pass
        elif bits == 16:
            left_wave = np.int16(left_wave / 2**16)
            right_wave = np.int16(right_wave / 2**16)
        elif bits == 8:
            left_wave = np.uint8(left_wave / 2**24 + 2**7)
            right_wave = np.uint8(right_wave / 2**24 + 2**7)
        else: raise ValueError(f"Illegal value {bits} for bits: only 8, 16, and 32 bits are available for decoding.")

        return np.column_stack((left_wave, right_wave))
    
    def internal(file_path, bits: int = 32):
        with open(file_path, 'rb') as f:
            header = f.read(256)

            signature = header[0x0:0xa]
            if signature != b'\x7e\x8b\xab\x89\xea\xc0\x9d\xa9\x68\x80':
                raise Exception('This is not Fourier Analogue file.')

            header_length = struct.unpack('<Q', header[0xa:0x12])[0]
            sample_rate = int.from_bytes(header[0x12:0x15], 'little')
            cfb = struct.unpack('<B', header[0x15:0x16])[0]
            cb = cfb >> 3
            fb = cfb & 0b111
            is_ecc_on = True if (struct.unpack('<B', header[0x16:0x17])[0] >> 7) == 0b1 else False
            checksum_header = header[0xf0:0x100]

            f.seek(header_length)

            data = f.read()
            checksum_data = hashlib.md5(data).digest()
            if is_ecc_on == False:
                if checksum_data == checksum_header:
                    pass
                else:
                    print(f'Checksum: on header[{checksum_header}] vs on data[{checksum_data}]')
                    raise Exception('File has corrupted but it has no ECC option. Decoder halted.')
            else:
                if checksum_data == checksum_header:
                    chunks = ecc.split_data(data, 148)
                    data =  b''.join([bytes(chunk[:128]) for chunk in chunks])
                else:
                    print(f'{file_path} has been corrupted, Please repack your file for the best music experience.')
                    print(f'Checksum: on header[{checksum_header}] vs on data[{checksum_data}]')
                    data = ecc.decode(data)

            # if b == 0b110:
            #     data_numpy = np.frombuffer(data, dtype=np.float512)
            # elif b == 0b101:
            #     data_numpy = np.frombuffer(data, dtype=np.float256)
            # elif b == 0b100:
            #     data_numpy = np.frombuffer(data, dtype=np.float128)
            if fb == 0b011:
                data_numpy = np.frombuffer(data, dtype=np.float64)
            elif fb == 0b010:
                data_numpy = np.frombuffer(data, dtype=np.float32)
            elif fb == 0b001:
                data_numpy = np.frombuffer(data, dtype=bfloat16)
            else:
                raise Exception('Illegal bits value.')

            if cb == 2:
                data_numpy = data_numpy.reshape(-1, 4)
                restored = decode.stereo(data_numpy, bits)
            elif cb == 1:
                data_numpy = data_numpy.reshape(-1, 2)
                restored = decode.mono(data_numpy, bits)
            else:
                raise Exception('Fourier Analogue only supports Mono and Stereo.')
            
            return restored, sample_rate

    def dec(file_path, out: str = None, bits: int = 32, codec: str = 'flac', bitrate: str = '4096k', quality: int = 10):
        restored, sample_rate = decode.internal(file_path, bits)
        out = out if out is not None else 'restored'
        out, ext = os.path.splitext(out)
        container = ext.lstrip('.').lower() if ext else codec

        channels = restored.shape[1] if len(restored.shape) > 1 else 1
        raw_audio = restored.tobytes()

        if codec == 'vorbis' or codec == 'opus':
            codec = 'lib' + codec

        if bits == 32:
            f = 's32le'
        elif bits == 16:
            f = 's16le'
        elif bits == 8:
            f = s = 'u8'
        else: raise ValueError(f"Illegal value {bits} for bits: only 8, 16, and 32 bits are available for decoding.")

        command = [
            'ffmpeg', '-y',
            '-loglevel', 'error',
            '-f', f,
            '-ar', str(sample_rate),
            '-ac', str(channels),
            '-i', 'pipe:0'
        ]
        if codec in ['pcm', 'wav', 'riff']:
            command.append('-c:a')
            command.append(f'pcm_{f}')
        else:
            command.append('-c:a')
            command.append(codec)
        if codec in ['libvorbis']:
            command.append('-q:a')
            command.append(str(quality))
        if codec in ['aac', 'm4a', 'mp3', 'libopus']:
            if codec == 'libopus' and int(bitrate.replace('k', '000')) > 512000:
                bitrate = '512k'
            command.append('-b:a')
            command.append(bitrate)
        command.append(f'{out}.{container}')
        subprocess.run(command, input=raw_audio)