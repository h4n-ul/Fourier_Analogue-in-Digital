from .decoder import decode
from .common import terminal

class player:
    @staticmethod
    def play(file_path, gain, keys: float | None = None, speed: float | None = None, e: bool = False, verbose: bool = False):
        if keys and speed: terminal('Keys and Speed parameter cannot be set at the same time.'); return
        elif keys and not speed: speed = 2**(keys/12)
        elif not keys and speed: pass
        else: speed = 1
        decode.internal(file_path, play=True, speed=speed, ecc=e, gain=gain, verbose=verbose)
