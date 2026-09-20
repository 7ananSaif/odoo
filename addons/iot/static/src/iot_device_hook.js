import { useService } from '@web/core/utils/hooks';
import { DeviceController } from '@iot_base/device_controller';
import { useEffect } from "@odoo/owl";

/**
 * Use this hook to be able to interact with an iot device.
 * @param {{
 *  getIotIp: () => string | undefined,
 *  getIdentifier: () => string | undefined,
 *  onValueChange: (data: any) => void,
 *  onStartListening: (() => void) | undefined,
 *  onStopListening: (() => void) | undefined,
 * }} param0
 */
export const useIotDevice = ({ getIotIp, getIdentifier, getLongpollingHasFallback, onValueChange, onStartListening, onStopListening }) => {
    // set default values for the device
    getIotIp = getIotIp || (() => {});
    getIdentifier = getIdentifier || (() => {});
    getLongpollingHasFallback = getLongpollingHasFallback || (() => false);
    onValueChange = onValueChange || (() => {});
    onStartListening = onStartListening || (() => {});
    onStopListening = onStopListening || (() => {});

    const iotLongpolling = useService('iot_longpolling');
    let iotDevice = null;

    const startListening = () => {
        iotDevice.addListener((data) => onValueChange(data), getLongpollingHasFallback());
        onStartListening();
    };

    const stopListening = () => {
        onStopListening();
        iotDevice.removeListener();
    };

    useEffect(
        (iotIp, identifier) => {
            if (iotIp && identifier) {
                iotDevice = new DeviceController(iotLongpolling, { iot_ip: iotIp, identifier });
                startListening();
                return () => {
                    stopListening();
                    iotDevice = null;
                };
            }
        },
        () => [getIotIp(), getIdentifier()]
    );

    return () => iotDevice;
};
