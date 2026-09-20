import { MapRenderer } from "@web_map/map_view/map_renderer";

export class StockMapRenderer extends MapRenderer {
    static markerPopupTemplate = "stock_enterprise.markerPopup";

    get googleMapUrl() {
        let url = super.googleMapUrl;
        if (this.props.model.data.records.length) {
            const warehouseAddress = this.props.model.data.records[0].warehouse_address_id;
            let multiAddresses = false;
            for (const record of this.props.model.data.records) {
                if (record.warehouse_address_id.id !== warehouseAddress.id) {
                    multiAddresses = true;
                    break;
                }
            }
            if (multiAddresses) {
                return url;
            }
            url += `&origin=${warehouseAddress.contact_address_complete}`;
            url += `&destination=${warehouseAddress.contact_address_complete}`;
        }
        return url;
    }

    getMarkerPopupData(markerInfo) {
        const records = markerInfo.relatedRecords.concat(markerInfo.record);
        const recordsView = [];

        for (const record of records) {
            recordsView.push({ fields: this.getMarkerPopupRecordData(record), id: record.id });
        }
        return recordsView;
    }
}
