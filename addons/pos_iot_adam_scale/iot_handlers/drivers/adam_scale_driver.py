# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import serial
import time

from odoo.addons.iot_drivers.event_manager import event_manager
from odoo.addons.iot_drivers.iot_handlers.drivers.serial_base_driver import SerialProtocol, serial_connection
from odoo.addons.iot_drivers.iot_handlers.drivers.serial_scale_driver import ScaleDriver


_logger = logging.getLogger(__name__)


# The ADAM scales have their own RS232 protocol, usually documented in the scale's manual
#   e.g at https://www.adamequipment.com/media/docs/Print%20Publications/Manuals/PDF/AZEXTRA/AZEXTRA-UM.pdf
#          https://www.manualslib.com/manual/879782/Adam-Equipment-Cbd-4.html?page=32#manual
# Only the baudrate and label format seem to be configurable in the AZExtra series.
ADAMEquipmentProtocol = SerialProtocol(
    name='Adam Equipment',
    baudrate=4800,
    bytesize=serial.EIGHTBITS,
    stopbits=serial.STOPBITS_ONE,
    parity=serial.PARITY_NONE,
    timeout=0.2,
    writeTimeout=0.2,
    measureRegexp=rb"\s*([0-9.]+)kg",  # LABEL format 3 + KG in the scale settings, but Label 1/2 should work
    statusRegexp=None,
    commandTerminator=b"\r\n",
    commandDelay=0.2,
    measureDelay=0.5,
    # AZExtra beeps every time you ask for a weight that was previously returned!
    # Adding an extra delay gives the operator a chance to remove the products
    # before the scale starts beeping. Could not find a way to disable the beeps.
    newMeasureDelay=5,
    measureCommand=b'P',
    emptyAnswerValid=True,  # AZExtra does not answer unless a new non-zero weight has been detected
)


class AdamEquipmentDriver(ScaleDriver):
    """Driver for the Adam Equipment serial scale."""

    _protocol = ADAMEquipmentProtocol
    priority = -1  # Test the supported method of this driver last, after all other serial drivers

    def __init__(self, identifier, device):
        super().__init__(identifier, device)
        self._is_reading = False
        self._last_weight_time = 0
        self.device_manufacturer = 'Adam'

    def _check_last_weight_time(self):
        """The ADAM doesn't make the difference between a value of 0 and "the same value as last time":
        in both cases it returns an empty string.
        With this, unless the weight changes, we give the user `TIME_WEIGHT_KEPT` seconds to log the new weight,
        then change it back to zero to avoid keeping it indefinetely, which could cause issues.
        In any case the ADAM must always go back to zero before it can weight again.
        """

        TIME_WEIGHT_KEPT = 10

        if self.data['value'] is None:
            if time.time() - self._last_weight_time > TIME_WEIGHT_KEPT:
                self.data['value'] = 0
        else:
            self._last_weight_time = time.time()

    def _take_measure(self):
        """Reads the device's weight value, and pushes that value to the frontend."""

        if self._is_reading:
            with self._device_lock:
                self._read_weight()
                self._check_last_weight_time()
                if self.data['value'] != self.last_sent_value or self._status['status'] == self.STATUS_ERROR:
                    self.last_sent_value = self.data['value']
                    event_manager.device_changed(self)
        else:
            time.sleep(0.5)

    # Ensures compatibility with Community edition
    def _scale_read_hw_proxy(self):
        """Used when the iot app is not installed"""

        time.sleep(3)
        with self._device_lock:
            self._read_weight()
            self._check_last_weight_time()
        return self.data['value']

    @classmethod
    def supported(cls, device):
        """Checks whether the device at `device` is supported by the driver.

        :param device: path to the device
        :type device: str
        :return: whether the device is supported by the driver
        :rtype: bool
        """

        protocol = cls._protocol

        try:
            with serial_connection(device['identifier'], protocol, is_probing=True) as connection:
                connection.write(protocol.measureCommand + protocol.commandTerminator)
                # Checking whether writing to the serial port using the Adam protocol raises a timeout exception is about the only thing we can do.
                #
                # Explanation:
                # - The serial connection for the Adam scales only sends data back after receiving the print ('P') command.
                #   - An attempt to find some other undocumented command (by trying every possible ASCII character) was unsuccessful.
                # - Sending this command is equivalent to pressing the 'Print' button on the device.
                # - It will only respond if the weight is non-zero, otherwise there will just be a double beep.
                # - It will also only give a double beep if the item has already been printed. You have to take the weight off and put it back again to print again.
                # - Therefore, there is no way for us to detect the scale automatically as it will only respond if a user actively weighs something.
                return True
        except serial.serialutil.SerialTimeoutException:
            pass
        except Exception:
            _logger.exception('Error while probing %s with protocol %s', device, protocol.name)
        return False

    def _read_status(self, answer):
        pass
