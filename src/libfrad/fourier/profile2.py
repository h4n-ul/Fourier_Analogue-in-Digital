from scipy.fft import dct, idct
import numpy as np
from .profiles import compact
from .tools import p1tools, p2tools
import struct, zlib

depths = (8, 12, 16, 20, 24, 28, 32)
dtypes = {32:'i4',28:'i4',24:'i4',20:'i4',16:'i2',12:'i2',8:'i1'}

@staticmethod
def analogue(pcm: np.ndarray, bits: int, channels: int, **kwargs) -> tuple[bytes, int, int]:
    # DCT
    pcm = np.pad(pcm, ((0, min((x for x in compact.SAMPLES_LI if x >= len(pcm)), default=len(pcm))-len(pcm)), (0, 0)), mode='constant')
    freqs = np.array([dct(pcm[:, i], norm='forward') for i in range(channels)]) * (2**(bits-1))

    # Quantisation
    tns_freqs, lpc = p2tools.tns.analysis(freqs)
    pns_freqs, pns_data = p2tools.pns.analysis(tns_freqs)

    # Ravelling and packing
    lpc_bytes = p1tools.exp_golomb_rice_encode(lpc.ravel().astype(int))
    pns_bytes = pns_data.astype('>f4').tobytes()
    frad: bytes = pns_freqs.ravel().astype(f'>{dtypes[bits]}').tobytes()
    frad = struct.pack(f'>I', len(lpc_bytes)) + lpc_bytes + pns_bytes + frad

    # Deflating
    frad = zlib.compress(frad)

    return frad, depths.index(bits), channels

@staticmethod
def digital(frad: bytes, fb: int, channels: int, **kwargs) -> np.ndarray:
    bits = depths[fb]

    # Inflating
    frad = zlib.decompress(frad)
    lpclen, frad = struct.unpack(f'>I', frad[:4])[0], frad[4:]
    lpc, frad = p1tools.exp_golomb_rice_decode(frad[:lpclen]).reshape(channels, -1), frad[lpclen:]

    pns_data, frad = np.frombuffer(frad[:channels*4], '>f4'), frad[channels*4:]

    # Unpacking
    freqs: np.ndarray = np.frombuffer(frad, f'>{dtypes[bits]}').astype(float).reshape(channels, -1)

    # Removing potential Infinities and Non-numbers
    freqs = np.where(np.isnan(freqs) | np.isinf(freqs), 0, freqs)

    # Dequantisation
    tns_freqs = p2tools.pns.synthesis(freqs, pns_data)
    rev_freqs = p2tools.tns.synthesis(tns_freqs, lpc)

    # Inverse DCT and stacking
    return np.ascontiguousarray(np.array([idct(chnl, norm='forward') for chnl in rev_freqs]).T) / (2**(bits-1))
