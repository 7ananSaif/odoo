export function mockFetchSpreadsheetHistory(resModel) {
    return function (resId, fromSnapshot = false) {
        const record = this.env[resModel].search_read([["id", "=", resId]])[0];
        if (!record) {
            throw new Error(`Spreadsheet ${resId} does not exist`);
        }
        return {
            name: record.name,
            data: JSON.parse(record.spreadsheet_data),
            revisions: [],
        };
    };
}
