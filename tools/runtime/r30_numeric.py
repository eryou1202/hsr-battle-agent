"""Offline transliteration of count packing at RVA 0x163ECE6E..0x163ECE90.

Returns native raw bits, never an R12/R19 value or a native scale assertion.
No runtime adapter imports this module.
"""
def pack_observed_count(count):
    if type(count) is not int or not -(1 << 31) <= count < (1 << 31):
        raise ValueError('signed int32 count required')
    bits = (count << 33) if abs(count) < (1 << 30) else ((count << 26) | 1)
    bits &= (1 << 64) - 1
    return bits - (1 << 64) if bits & (1 << 63) else bits
