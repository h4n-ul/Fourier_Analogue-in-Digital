import numpy as np
import struct

# Modified Opus Subbands
MOS =  (0,     200,   400,   600,   800,   1000,  1200,  1400,
        1600,  2000,  2400,  2800,  3200,  4000,  4800,  5600,
        6800,  8000,  9600,  12000, 15600, 20000, 24000, 28800,
        34400, 40800, 48000, (2**32)-1)

subbands = len(MOS) - 1
rndint = lambda x: int(x+0.5)
spread_alpha = 0.8
quant_alpha = 0.75

class subband:
    @staticmethod
    def get_bin_range(dlen: int, srate: int, subband_index: int) -> slice:
        return slice(rndint(dlen/(srate/2)*MOS[subband_index]), rndint(dlen/(srate/2)*MOS[subband_index+1]))

    @staticmethod
    def mask_thres_mos(freqs: np.ndarray, alpha: float) -> np.ndarray:
        thres = np.zeros_like(freqs)
        for i in range(subbands):
            f = (MOS[i] + MOS[i+1]) / 2
            ABS = (3.64*(f/1000.)**-0.8 - 6.5*np.exp(-0.6*(f/1000.-3.3)**2.) + 1e-3*((f/1000.)**4.))
            ABS = np.clip(ABS, None, 96)
            thres[i] = np.maximum(freqs[i]**alpha, 10.0**((ABS-96)/20))
        return thres

    @staticmethod
    def mapping_to_opus(freqs: np.ndarray, srate):
        mapped_freqs = np.zeros(subbands)
        for i in range(subbands):
            subfreqs = freqs[subband.get_bin_range(len(freqs), srate, i)]
            if len(subfreqs) > 0: mapped_freqs[i] = np.sqrt(np.mean(subfreqs**2))
        return mapped_freqs

    @staticmethod
    def mapping_from_opus(mapped_freqs, freqs_shape, srate):
        freqs = np.zeros(freqs_shape)
        for i in range(subbands-1): 
            start = min(subband.get_bin_range(freqs_shape, srate, i).start, len(freqs))
            end = min(subband.get_bin_range(freqs_shape, srate, i+1).start, len(freqs))
            freqs[start:end] = np.linspace(mapped_freqs[i], mapped_freqs[i+1], end-start)
        return freqs

def quant(x): return np.sign(x) * np.abs(x)**quant_alpha
def dequant(x): return np.sign(x) * np.abs(x)**(1/quant_alpha)

bitstr2bytes = lambda bstr: bytes(int(bstr[i:i+8].ljust(8, '0'), 2) for i in range(0, len(bstr), 8))
bytes2bitstr = lambda b: ''.join(f'{byte:08b}' for byte in b)

def exp_golomb_rice_encode(data: np.ndarray):
    if not data.size: return b'\x00'
    dmax = np.abs(data).max()
    k = dmax and int(np.ceil(np.log2(dmax))) or 0
    encoded = ''
    for n in data:
        n = (n>0) and (2*n-1) or (-2*n)
        binary_code = bin(n + 2**k)[2:]
        m = len(binary_code) - (k+1)
        encoded += ('0' * m + binary_code)

    return struct.pack('B', k) + bitstr2bytes(encoded)

def exp_golomb_rice_decode(dbytes: bytes):
    k = struct.unpack('B', dbytes[:1])[0]
    decoded = []
    data = bytes2bitstr(dbytes[1:])
    while data:
        try: m = data.index('1')
        except: break

        codeword, data = data[:(m*2)+k+1], data[(m*2)+k+1:]
        n = int(codeword, 2) - 2**k
        decoded.append((n+1)//2 if n%2==1 else -n//2)

    return np.array(decoded)
