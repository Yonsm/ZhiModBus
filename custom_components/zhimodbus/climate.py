"""
Platform for a Generic Modbus Thermostat.

For more details about this platform, please refer to the documentation at
https://yonsm.github.io/modbus
"""

import logging
import struct

import voluptuous as vol

from homeassistant.components.climate import ClimateEntity, PLATFORM_SCHEMA
from homeassistant.components.climate.const import (
    SUPPORT_AUX_HEAT, SUPPORT_FAN_MODE, SUPPORT_PRESET_MODE, SUPPORT_SWING_MODE,
    SUPPORT_TARGET_HUMIDITY, SUPPORT_TARGET_TEMPERATURE,
    HVAC_MODE_OFF, HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_HEAT_COOL,
    HVAC_MODE_AUTO,  HVAC_MODE_DRY, HVAC_MODE_FAN_ONLY,
    CURRENT_HVAC_OFF, CURRENT_HVAC_HEAT, CURRENT_HVAC_COOL, CURRENT_HVAC_IDLE,
    CURRENT_HVAC_DRY, CURRENT_HVAC_FAN,
)
from homeassistant.const import (
    CONF_NAME, CONF_SLAVE, CONF_OFFSET, CONF_STRUCTURE, ATTR_TEMPERATURE)
from homeassistant.components.modbus.const import (
    CONF_HUB, DEFAULT_HUB, MODBUS_DOMAIN)
from homeassistant.helpers.event import async_call_later
import homeassistant.components.modbus as modbus
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['modbus']

CONF_AUX_HEAT_OFF_VALUE = 'aux_heat_off_value'
CONF_AUX_HEAT_ON_VALUE = 'aux_heat_on_value'
CONF_COUNT = 'count'
CONF_DATA_TYPE = 'data_type'
CONF_FAN_MODES = 'fan_modes'
CONF_HVAC_MODES = 'hvac_modes'
CONF_HVAC_OFF_VALUE = 'hvac_off_value'
CONF_HVAC_ON_VALUE = 'hvac_on_value'
CONF_PRESET_MODES = 'preset_mode'
CONF_REGISTER = 'register'
CONF_REGISTER_TYPE = 'register_type'
CONF_REGISTERS = 'registers'
CONF_REVERSE_ORDER = 'reverse_order'
CONF_SCALE = 'scale'
CONF_SWING_MODES = 'swing_modes'

REG_AUX_HEAT = 'aux_heat'
REG_FAN_MODE = 'fan_mode'
REG_HUMIDITY = 'humidity'
REG_HVAC_MODE = 'hvac_mode'
REG_HVAC_OFF = 'hvac_off'
REG_PRESET_MODE = 'preset_mode'
REG_SWING_MODE = 'swing_mode'
REG_TARGET_HUMIDITY = 'target_humidity'
REG_TARGET_TEMPERATURE = 'target_temperature'
REG_TEMPERATURE = 'temperature'

REGISTER_TYPE_HOLDING = 'holding'
REGISTER_TYPE_INPUT = 'input'
REGISTER_TYPE_COIL = 'coil'

DATA_TYPE_INT = 'int'
DATA_TYPE_UINT = 'uint'
DATA_TYPE_FLOAT = 'float'
DATA_TYPE_CUSTOM = 'custom'

SUPPORTED_FEATURES = {
    REG_AUX_HEAT: SUPPORT_AUX_HEAT,
    REG_FAN_MODE: SUPPORT_FAN_MODE,
    REG_HUMIDITY: 0,
    REG_HVAC_MODE: 0,
    REG_HVAC_OFF: 0,
    REG_PRESET_MODE: SUPPORT_PRESET_MODE,
    REG_SWING_MODE: SUPPORT_SWING_MODE,
    REG_TARGET_HUMIDITY: SUPPORT_TARGET_HUMIDITY,
    REG_TARGET_TEMPERATURE: SUPPORT_TARGET_TEMPERATURE,
    REG_TEMPERATURE: 0,
}

HVAC_ACTIONS = {
    HVAC_MODE_OFF: CURRENT_HVAC_OFF,
    HVAC_MODE_HEAT: CURRENT_HVAC_HEAT,
    HVAC_MODE_COOL: CURRENT_HVAC_COOL,
    HVAC_MODE_HEAT_COOL: CURRENT_HVAC_IDLE,
    HVAC_MODE_AUTO: CURRENT_HVAC_IDLE,
    HVAC_MODE_DRY: CURRENT_HVAC_DRY,
    HVAC_MODE_FAN_ONLY: CURRENT_HVAC_FAN,
}

DEFAULT_NAME = 'ModBus'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): vol.Any(cv.string, list),

    vol.Optional(CONF_FAN_MODES, default={}): dict,
    vol.Optional(CONF_HVAC_MODES, default={}): dict,
    vol.Optional(CONF_PRESET_MODES, default={}): dict,
    vol.Optional(CONF_SWING_MODES, default={}): dict,
    vol.Optional(CONF_AUX_HEAT_OFF_VALUE, default=0): int,
    vol.Optional(CONF_AUX_HEAT_ON_VALUE, default=1): int,
    vol.Optional(CONF_HVAC_OFF_VALUE, default=0): int,
    vol.Optional(CONF_HVAC_ON_VALUE, default=1): int,

    vol.Optional(REG_AUX_HEAT): dict,
    vol.Optional(REG_FAN_MODE): dict,
    vol.Optional(REG_HUMIDITY): dict,
    vol.Optional(REG_HVAC_MODE): dict,
    vol.Optional(REG_HVAC_OFF): dict,
    vol.Optional(REG_PRESET_MODE): dict,
    vol.Optional(REG_SWING_MODE): dict,
    vol.Optional(REG_TARGET_HUMIDITY): dict,
    vol.Optional(REG_TARGET_TEMPERATURE): dict,
    vol.Optional(REG_TEMPERATURE): dict,
})


def setup_platform(hass, conf, add_devices, discovery_info=None):
    """Set up the Modbus Thermostat Platform."""
    name = conf.get(CONF_NAME)
    bus = ClimateModbus(hass, conf)
    if not bus.regs:
        _LOGGER.error("Invalid config %s: no modbus items", name)
        return

    entities = []
    for index in range(100):
        if not bus.has_valid_register(index):
            break
        entities.append(ModbusClimate(bus, name[index] if isinstance(name, list) else (name + str(index + 1)), index))

    if not entities:
        for prop in bus.regs:
            if CONF_REGISTER not in bus.regs[prop]:
                _LOGGER.error("Invalid config %s/%s: no register", name, prop)
                return
        entities.append(ModbusClimate(bus, name[0] if isinstance(name, list) else name))

    bus.count = len(entities)
    add_devices(entities, True)


class ClimateModbus():

    def __init__(self, hass, conf):
        self.error = 0
        self.hub = hass.data[MODBUS_DOMAIN][conf.get(CONF_HUB)]
        self.unit = hass.config.units.temperature_unit
        self.fan_modes = conf.get(CONF_FAN_MODES)
        self.hvac_modes = conf.get(CONF_HVAC_MODES)
        self.preset_modes = conf.get(CONF_PRESET_MODES)
        self.swing_modes = conf.get(CONF_SWING_MODES)
        self.hvac_off_value = conf.get(CONF_HVAC_OFF_VALUE)
        self.hvac_on_value = conf.get(CONF_HVAC_ON_VALUE)
        self.aux_heat_on_value = conf.get(CONF_AUX_HEAT_ON_VALUE)
        self.aux_heat_off_value = conf.get(CONF_AUX_HEAT_OFF_VALUE)

        data_types = {DATA_TYPE_INT: {1: 'h', 2: 'i', 4: 'q'}}
        data_types[DATA_TYPE_UINT] = {1: 'H', 2: 'I', 4: 'Q'}
        data_types[DATA_TYPE_FLOAT] = {1: 'e', 2: 'f', 4: 'd'}

        self.regs = {}
        for prop in SUPPORTED_FEATURES:
            reg = conf.get(prop)
            if not reg:
                continue

            count = reg.get(CONF_COUNT, 1)
            data_type = reg.get(CONF_DATA_TYPE)
            if data_type != DATA_TYPE_CUSTOM:
                try:
                    reg[CONF_STRUCTURE] = '>{}'.format(data_types[DATA_TYPE_INT if data_type is None else data_type][count])
                except KeyError:
                    _LOGGER.error("Unable to detect data type for %s", prop)
                    continue

            try:
                size = struct.calcsize(reg[CONF_STRUCTURE])
            except struct.error as err:
                _LOGGER.error("Error in sensor %s structure: %s", prop, err)
                continue

            if count * 2 != size:
                _LOGGER.error("Structure size (%d bytes) mismatch registers count (%d words)", size, count)
                continue

            self.regs[prop] = reg

    def has_valid_register(self, index):
        """Check valid register."""
        for prop in self.regs:
            registers = self.regs[prop].get(CONF_REGISTERS)
            if not registers or index >= len(registers):
                return False
        return True

    def reset(self):
        """Initialize USR module"""
        _LOGGER.warn("Reset %s", self.hub._client)
        import socket
        import time
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((self.hub._client.host, self.hub._client.port))
        s.sendall(b'\x55\xAA\x55\x00\x25\x80\x03\xA8')
        s.close()
        time.sleep(1)

    def reconnect(self):
        _LOGGER.warn("Reconnect %s", self.hub._client)
        from pymodbus.client.sync import ModbusTcpClient as ModbusClient
        from pymodbus.transaction import ModbusRtuFramer as ModbusFramer
        self.hub._client.close()
        self.hub._client = ModbusClient(
            host=self.hub._client.host,
            port=self.hub._client.port,
            framer=ModbusFramer,
            timeout=self.hub._client.timeout)
        self.hub._client.connect()

    def exception(self):
        turns = int(self.error / self.count)
        self.error += 1
        if turns == 0 or (turns > 6 and turns % 10):
            return
        if turns % 3 == 0:
            self.reset()
        self.reconnect()

    def reg_basic_info(self, reg, index):
        """Get register info."""
        register_type = reg.get(CONF_REGISTER_TYPE)
        register = reg[CONF_REGISTER] if index == -1 else reg[CONF_REGISTERS][index]
        slave = reg.get(CONF_SLAVE, 1)
        scale = reg.get(CONF_SCALE, 1)
        offset = reg.get(CONF_OFFSET, 0)
        return (register_type, slave, register, scale, offset)

    def read_value(self, index, prop):
        reg = self.regs[prop]
        register_type, slave, register, scale, offset = self.reg_basic_info(reg, index)
        count = reg.get(CONF_COUNT, 1)
        if register_type == REGISTER_TYPE_COIL:
            result = self.hub.read_coils(slave, register, count)
            return bool(result.bits[0])
        if register_type == REGISTER_TYPE_INPUT:
            result = self.hub.read_input_registers(slave, register, count)
        else:
            result = self.hub.read_holding_registers(slave, register, count)
        val = 0
        registers = result.registers
        if reg.get(CONF_REVERSE_ORDER):
            registers.reverse()
        byte_string = b''.join([x.to_bytes(2, byteorder='big') for x in registers])
        val = struct.unpack(reg[CONF_STRUCTURE], byte_string)[0]
        value = scale * val + offset
        #_LOGGER.debug("Read %d: %s = %f at %s/slave%s/register%s", index, prop, value, register_type, slave, register)
        return value

    def write_value(self, index, prop, value):
        """Set property value."""
        reg = self.regs[prop]
        register_type, slave, register, scale, offset = self.reg_basic_info(reg, index)
        if register_type == REGISTER_TYPE_COIL:
            self.hub.write_coil(slave, register, bool(value))
        else:
            val = (value - offset) / scale
            self.hub.write_register(slave, register, int(val))


class ModbusClimate(ClimateEntity):
    """Representation of a Modbus climate device."""

    def __init__(self, bus, name, index=-1):
        """Initialize the climate device."""
        self._bus = bus
        self._name = name
        self._index = index
        self._values = {}
        self._last_on_operation = None
        self._skip_update = False

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def supported_features(self):
        """Return the list of supported features."""
        features = 0
        for prop in self._bus.regs:
            features |= SUPPORTED_FEATURES[prop]
        return features

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._bus.unit

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.get_value(REG_TEMPERATURE)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.get_value(REG_TARGET_TEMPERATURE)

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self.get_value(REG_HUMIDITY)

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self.get_value(REG_TARGET_HUMIDITY)

    @property
    def hvac_action(self):
        """Return current operation ie. heat, cool, idle."""
        return HVAC_ACTIONS[self.hvac_mode]

    @property
    def hvac_mode(self):
        if REG_HVAC_OFF in self._bus.regs:
            if self.get_value(REG_HVAC_OFF) == self._bus.hvac_off_value:
                return HVAC_MODE_OFF
        hvac_mode = self.get_mode(self._bus.hvac_modes, REG_HVAC_MODE) or HVAC_MODE_OFF
        if hvac_mode != HVAC_MODE_OFF:
            self._last_on_operation = hvac_mode
        return hvac_mode

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return list(self._bus.hvac_modes)

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self.get_mode(self._bus.fan_modes, REG_FAN_MODE)

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return list(self._bus.fan_modes)

    @property
    def swing_mode(self):
        """Return the swing setting."""
        return self.get_mode(self._bus.swing_modes, REG_SWING_MODE)

    @property
    def swing_modes(self):
        """List of available swing modes."""
        return list(self._bus.swing_modes)

    @property
    def preset_mode(self):
        """Return preset mode setting."""
        return self.get_value(REG_PRESET_MODE)

    @property
    def preset_modes(self):
        """List of available swing modes."""
        return list(self._bus.preset_modes)

    @property
    def is_aux_heat(self):
        """Return true if aux heat is on."""
        return self.get_value(REG_AUX_HEAT) == self._bus.aux_heat_on_value

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            self.set_value(REG_TARGET_TEMPERATURE, temperature)

        # hvac_mode = kwargs.get('hvac_mode')
        # if hvac_mode is not None:
        #     self.set_hvac_mode(hvac_mode)

    def set_humidity(self, humidity):
        """Set new target humidity."""
        self.set_value(REG_TARGET_HUMIDITY, humidity)

    def set_hvac_mode(self, hvac_mode):
        """Set new hvac mode."""
        if REG_HVAC_OFF in self._bus.regs:
            self.set_value(REG_HVAC_OFF, self._bus.hvac_off_value if hvac_mode == HVAC_MODE_OFF else self._bus.hvac_on_value)
            if hvac_mode == HVAC_MODE_OFF:
                return

        if hvac_mode not in self._bus.hvac_modes:  # Support HomeKit Auto Mode
            best_hvac_mode = self.best_hvac_mode
            _LOGGER.warn("Fix operation mode from %s to %s", hvac_mode, best_hvac_mode)
            hvac_mode = best_hvac_mode
            # current = self.current_temperature
            # target = self.target_temperature
            # hvac_mode = HVAC_MODE_HEAT if current and target and current < target else HVAC_MODE_COOL

        self.set_mode(self._bus.hvac_modes, REG_HVAC_MODE, hvac_mode)

    @property
    def best_hvac_mode(self):
        for mode in (HVAC_MODE_HEAT_COOL, HVAC_MODE_COOL, HVAC_MODE_HEAT):
            if mode in self._bus.hvac_modes:
                return mode
        return None

    def turn_on(self):
        """Turn on."""
        _LOGGER.debug("Turn on with last operation mode: %s", self._last_on_operation)
        self.set_hvac_mode(self._last_on_operation or self.best_hvac_mode)

    def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        self.set_mode(self._fan_modes, REG_FAN_MODE, fan_mode)

    def set_swing_mode(self, swing_mode):
        """Set new swing mode."""
        self.set_mode(self._swing_modes, REG_SWING_MODE, swing_mode)

    def set_preset_mode(self, preset_mode):
        """Set new hold mode."""
        self.set_value(REG_PRESET_MODE, preset_mode)

    def turn_aux_heat_on(self):
        """Turn auxiliary heater on."""
        self.set_value(REG_AUX_HEAT, self._bus.aux_heat_on_value)

    def turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        self.set_value(REG_AUX_HEAT, self._bus.aux_heat_off_value)

    def update(self):
        """Update state."""
        if self._skip_update:
            self._skip_update = False
            _LOGGER.debug("Skip update on %s", self._name)
            return

        _LOGGER.debug("Update on %s", self._name)
        for prop in self._bus.regs:
            try:
                self._values[prop] = self._bus.read_value(self._index, prop)
            except:
                self._bus.exception()
                _LOGGER.debug("Exception %d on %s/%s", self._bus.error, self._name, prop)
                return
        self._bus.error = 0

    def get_value(self, prop):
        """Get property value."""
        return self._values.get(prop)

    def set_value(self, prop, value):
        """Set property value."""
        _LOGGER.debug("Write %s: %s = %f", self.name, prop, value)
        self._skip_update = True
        self._bus.write_value(self._index, prop, value)
        self._values[prop] = value
        # self.async_write_ha_state()
        # async_call_later(self.hass, 2, self.async_schedule_update_ha_state)

    def get_mode(self, modes, prop):
        value = self.get_value(prop)
        if value is not None:
            for k, v in modes.items():
                if v == value:
                    #_LOGGER.debug("get_mode: %s for %s", k, prop)
                    return k
        _LOGGER.error("Invalid value %s for %s/%s", value, self._name, prop)
        return None

    def set_mode(self, modes, prop, mode):
        if mode in modes:
            self.set_value(prop, modes[mode])
            return
        _LOGGER.error("Invalid mode %s for %s/%s", mode, self._name, prop)
