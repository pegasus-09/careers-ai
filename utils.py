from enum import Enum

def clamp(value):
    if value < 0:
        value = 0.0
    elif value > 1:
        value = 1.0
    return value
