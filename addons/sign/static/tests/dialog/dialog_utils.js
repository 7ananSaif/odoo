export const fakeSignInfoService = (signInfo) => ({
    get(key) {
        return signInfo[key];
    },
});
