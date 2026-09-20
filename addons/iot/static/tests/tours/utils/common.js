/**
 * Browser can be killed before the IoT request (longpolling, websocket, ...)
 * has been performed. This step adds a 1s delay
 */
export function waitForIotRequest(delay = 1000) {
    return {
        trigger: 'body',
        run: async () => {
            await new Promise(resolve => setTimeout(resolve, delay));
        },
    }
}
