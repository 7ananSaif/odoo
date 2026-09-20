let i = 0;
function createBoxData(params) {
    return {
        id: i++,
        page: 0,
        text: params.text,
        angle: 0, // no angle
        width: params.width,
        height: params.height,
        minX: params.midX - params.width / 2,
        midX: params.midX,
        maxX: params.midX + params.width / 2,
        minY: params.midY - params.height / 2,
        midY: params.midY,
        maxY: params.midY + params.height / 2,
    };
}

// Check the attachment.png file to visualize this data
export function getBoxesData() {
    const wordBoxes = {
        "0": [
            createBoxData({
                text: "Hello",
                midX: 0.2,
                midY: 0.1,
                width: 0.119,
                height: 0.027,
            }),
            createBoxData({
                text: "world",
                midX: 0.35,
                midY: 0.1,
                width: 0.124,
                height: 0.027,
            }),
            createBoxData({
                text: "USD",
                midX: 0.9,
                midY: 0.2,
                width: 0.095,
                height: 0.027,
            }),
            createBoxData({
                text: "First",
                midX: 0.05,
                midY: 0.35,
                width: 0.095,
                height: 0.027,
            }),
            createBoxData({
                text: "line",
                midX: 0.16,
                midY: 0.35,
                width: 0.09,
                height: 0.027,
            }),
            createBoxData({
                text: "Second",
                midX: 0.09,
                midY: 0.41,
                width: 0.167,
                height: 0.027,
            }),
            createBoxData({
                text: "line",
                midX: 0.23,
                midY: 0.41,
                width: 0.09,
                height: 0.027,
            }),
            createBoxData({
                text: "with",
                midX: 0.35,
                midY: 0.41,
                width: 0.1,
                height: 0.027,
            }),
            createBoxData({
                text: "continuation",
                midX: 0.15,
                midY: 0.45,
                width: 0.286,
                height: 0.027,
            }),
            createBoxData({
                text: "line",
                midX: 0.36,
                midY: 0.45,
                width: 0.09,
                height: 0.027,
            }),
            createBoxData({
                text: "Third",
                midX: 0.06,
                midY: 0.51,
                width: 0.124,
                height: 0.027,
            }),
            createBoxData({
                text: "line",
                midX: 0.18,
                midY: 0.51,
                width: 0.09,
                height: 0.027,
            }),
        ],
    };
    const numberBoxes = {
        "0": [
            createBoxData({
                text: 123.45,
                midX: 0.6,
                midY: 0.1,
                width: 0.152,
                height: 0.027,
            }),
            createBoxData({
                text: 67.89,
                midX: 0.8,
                midY: 0.1,
                width: 0.124,
                height: 0.027,
            }),
            createBoxData({
                text: 12,
                midX: 0.95,
                midY: 0.1,
                width: 0.057,
                height: 0.027,
            }),
            createBoxData({
                text: 28.08,
                midX: 0.92,
                midY: 0.35,
                width: 0.124,
                height: 0.027,
            }),
            createBoxData({
                text: 19.95,
                midX: 0.92,
                midY: 0.41,
                width: 0.124,
                height: 0.027,
            }),
            createBoxData({
                text: 12.00,
                midX: 0.92,
                midY: 0.51,
                width: 0.124,
                height: 0.027,
            }),
        ],
    };
    const dateBoxes = {
        "0": [
            createBoxData({
                text: "2020-01-01",
                midX: 0.25,
                midY: 0.2,
                width: 0.257,
                height: 0.027,
            }),
            createBoxData({
                text: "2020-01-15",
                midX: 0.6,
                midY: 0.2,
                width: 0.257,
                height: 0.027,
            }),
            createBoxData({
                text: "2020-01-03",
                midX: 0.6,
                midY: 0.35,
                width: 0.257,
                height: 0.027,
            }),
            createBoxData({
                text: "2020-01-07",
                midX: 0.6,
                midY: 0.41,
                width: 0.257,
                height: 0.027,
            }),
            createBoxData({
                text: "2020-01-13",
                midX: 0.6,
                midY: 0.51,
                width: 0.257,
                height: 0.027,
            }),
        ],
    };
    return {
        'word': wordBoxes,
        'number': numberBoxes,
        'date': dateBoxes,
    }
}
