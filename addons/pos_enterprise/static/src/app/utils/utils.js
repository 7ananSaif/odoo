import { useState, useEffect } from "@odoo/owl";

export const computeFontColor = (bgColor) => {
    if (!bgColor) {
        return "black";
    }

    var hexAr = bgColor.replace("#", "").match(/.{1,2}/g);
    var rgb = hexAr.map((col) => parseInt(col, 16));
    return (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255 > 0.5 ? "black" : "white";
};

export function useDelayedValueChange(getCurrentValue, duration = 5000) {
    const state = useState({
        oldValue: getCurrentValue(),
    });
    let timeout = null;
    useEffect(
        () => {
            timeout = setTimeout(() => {
                state.oldValue = getCurrentValue();
            }, duration);
            return () => clearTimeout(timeout);
        },
        () => [getCurrentValue()]
    );
    return {
        get isActive() {
            return state.oldValue != getCurrentValue();
        },
    };
}

export const computeDurationSinceDate = (startDateTime) => {
    const timeDiff = (luxon.DateTime.now().ts - startDateTime.ts) / 1000;
    return Math.floor(timeDiff / 60);
};
