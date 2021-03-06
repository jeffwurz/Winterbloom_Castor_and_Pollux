# Interface for Gemini's MIDI SysEx command set

from dataclasses import dataclass
import enum
import struct

import rtmidi.midiutil

SYSEX_START = 0xF0
SYSEX_END = 0xF7
SYSEX_MARKER = 0x77

def _wait_for_message(port_in):
    while True:
        msg = port_in.get_message()
        if msg:
            msg, _ = msg
            return msg


def _fix16(val):
    if val >= 0:
        return int(x * 65536.0 + 0.5)
    else:
        return int(x * 65536.0 - 0.5)


@dataclass
class Settings:
    LENGTH: int = 49

    magic: int = 0
    adc_gain_corr: int = 0
    adc_offset_corr: int = 0
    led_brightness: int = 0
    castor_knob_min: int = 0
    castor_knob_max: int = 0
    pollux_knob_min: int = 0
    pollux_knob_max: int = 0
    chorus_max_intensity: int = 0
    chorus_frequency: int = 0
    knob_offset_corr: int = 0
    knob_gain_corr: int = 0
    smooth_initial_gain: int = 0
    smooth_sensitivity: int = 0
    pollux_follower_threshold: int = 0


class SysExCommands(enum.IntEnum):
    HELLO = 0x01
    WRITE_ADC_GAIN = 0x02
    WRITE_ADC_OFFSET = 0x03
    READ_ADC = 0x04
    SET_DAC = 0x05
    SET_FREQ = 0x06
    RESET_SETTINGS = 0x07
    READ_SETTINGS = 0x08
    WRITE_SETTINGS = 0x09
    WRITE_LUT_ENTRY = 0x0A
    WRITE_LUT = 0x0B
    ERASE_LUT = 0x0C
    DISABLE_ADC_CORR = 0x0D
    ENABLE_ADC_CORR = 0x0E


def midi_encode(src, dst):
    for n in range(len(src)):
        dst[n * 2] = src[n] >> 4 & 0xF;
        dst[n * 2 + 1] = src[n] & 0xF;


def midi_decode(src, dst):
    for n in range(len(dst)):
        dst[n] = src[n * 2] << 4 | src[n * 2 + 1];


class Gemini:
    MIDI_PORT_NAME = "Gemini"

    def __init__(self):
        self.port_in, _ = rtmidi.midiutil.open_midiport(self.MIDI_PORT_NAME, type_="input")
        self.port_in.ignore_types(sysex=False)
        self.port_out, _ = rtmidi.midiutil.open_midiport(self.MIDI_PORT_NAME, type_="output")

    def enter_calibration_mode(self):
        self.port_out.send_message([
            SYSEX_START, SYSEX_MARKER, SysExCommands.HELLO, SYSEX_END])
        msg = _wait_for_message(self.port_in)
        print(f"Gemini version: {msg[3]}")

    def read_adc(self, ch):
        self.port_out.send_message([
            SYSEX_START, SYSEX_MARKER, SysExCommands.READ_ADC, ch, SYSEX_END])
        msg = _wait_for_message(self.port_in)
        val = (msg[3] << 16 | msg[4] << 8 | msg[5] << 4 | msg[6])
        return val

    def set_dac(self, ch, val, gain):
        self.port_out.send_message([
            SYSEX_START, SYSEX_MARKER, SysExCommands.SET_DAC,
            ch,
            gain,
            (val >> 12) & 0xF, (val >> 8) & 0xF, (val >> 4) & 0xF, val & 0xF,
            SYSEX_END])

    def set_period(self, ch, val):
        self.port_out.send_message([
            SYSEX_START, SYSEX_MARKER, SysExCommands.SET_FREQ,
            ch,
            (val >> 12) & 0xF, (val >> 8) & 0xF, (val >> 4) & 0xF, val & 0xF,
            SYSEX_END])

    def set_adc_gain_error_int(self, val):
        self.port_out.send_message([
            SYSEX_START, SYSEX_MARKER, SysExCommands.WRITE_ADC_GAIN,
            (val >> 12) & 0xF, (val >> 8) & 0xF, (val >> 4) & 0xF, val & 0xF,
            SYSEX_END])
    
    def set_adc_gain_error(self, val):
        val = int(val * 2048)
        self.set_adc_gain_error_int(val)

    def set_adc_offset_error(self, val):
        self.port_out.send_message([
            SYSEX_START, SYSEX_MARKER, SysExCommands.WRITE_ADC_OFFSET,
            (val >> 12) & 0xF, (val >> 8) & 0xF, (val >> 4) & 0xF, val & 0xF,
            SYSEX_END])

    def disable_adc_error_correction(self):
        self.port_out.send_message([
            SYSEX_START, SYSEX_MARKER, SysExCommands.DISABLE_ADC_CORR, SYSEX_END])

    def enable_adc_error_correction(self):
        self.port_out.send_message([
            SYSEX_START, SYSEX_MARKER, SysExCommands.ENABLE_ADC_CORR, SYSEX_END])

    def reset_settings(self):
        self.port_out.send_message([
            SYSEX_START, SYSEX_MARKER, SysExCommands.RESET_SETTINGS, SYSEX_END])

    def read_settings(self):
        settings_encoded = bytearray(128)
        for n in range(8):
            self.port_out.send_message([
                SYSEX_START, SYSEX_MARKER, SysExCommands.READ_SETTINGS, n, SYSEX_END])
            msg = _wait_for_message(self.port_in)
            settings_encoded[16 * n: 16 * n + 16] = msg[3:-1]

        settings_buf = bytearray(64)
        midi_decode(settings_encoded, settings_buf)
        settings = Settings()

        (settings.magic,
        settings.adc_gain_corr,
        settings.adc_offset_corr,
        settings.led_brightness,
        settings.castor_knob_min,
        settings.castor_knob_max,
        settings.pollux_knob_min,
        settings.pollux_knob_max,
        settings.chorus_max_intensity,
        settings.chorus_frequency,
        settings.knob_offset_corr,
        settings.knob_gain_corr,
        settings.smooth_initial_gain,
        settings.smooth_sensitivity,
        settings.pollux_follower_threshold,) = struct.unpack(">BHhHiiiiiiiiiiH", settings_buf[:Settings.LENGTH])

        return settings

    def save_settings(self, settings):
        settings_buf = bytearray(struct.pack(
            ">BHhHiiiiiiiiiiH",
            settings.magic,
            settings.adc_gain_corr,
            settings.adc_offset_corr,
            settings.led_brightness,
            settings.castor_knob_min,
            settings.castor_knob_max,
            settings.pollux_knob_min,
            settings.pollux_knob_max,
            settings.chorus_max_intensity,
            settings.chorus_frequency,
            settings.knob_offset_corr,
            settings.knob_gain_corr,
            settings.smooth_initial_gain,
            settings.smooth_sensitivity,
            settings.pollux_follower_threshold))

        settings_encoded = bytearray(128)
        midi_encode(settings_buf, settings_encoded)

        for n in range(8):
            #print(' '.join(f"{x:02x}" for x in settings_encoded[16 * n: 16 * n + 16]))
            self.port_out.send_message(
                bytearray([SYSEX_START, SYSEX_MARKER, SysExCommands.WRITE_SETTINGS, n]) +
                settings_encoded[16 * n: 16 * n + 16] +
                bytearray([SYSEX_END]))
            # Wait for ack
            _wait_for_message(self.port_in)

    def write_lut_entry(self, entry, castor_pollux, val):
        self.port_out.send_message([
            SYSEX_START, SYSEX_MARKER, SysExCommands.WRITE_LUT_ENTRY,
            entry, castor_pollux,
            (val >> 12) & 0xF, (val >> 8) & 0xF, (val >> 4) & 0xF, val & 0xF, SYSEX_END])
        # wait for ack
        _wait_for_message(self.port_in)

    def write_lut(self):
        self.port_out.send_message([
            SYSEX_START, SYSEX_MARKER, SysExCommands.WRITE_LUT, SYSEX_END])

    def erase_lut(self):
        self.port_out.send_message([
            SYSEX_START, SYSEX_MARKER, SysExCommands.ERASE_LUT, SYSEX_END])