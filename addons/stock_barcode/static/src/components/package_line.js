import LineComponent from "./line";

export default class PackageLineComponent extends LineComponent {
    static props = ["displayUOM", "line", "openPackage"];
    static template = "stock_barcode.PackageLineComponent";

    get isComplete() {
        return this.qtyDone == this.qtyDemand;
    }

    get isSelected() {
        return this.line.package_id.id === this.env.model.lastScanned.packageId;
    }

    get qtyDemand() {
        return this.props.line.reserved_uom_qty ? 1 : 0;
    }

    get qtyDone() {
        const reservedQuantity = this.line.lines.reduce((r, l) => r + l.reserved_uom_qty, 0);
        const doneQuantity = this.line.lines.reduce((r, l) => r + l.qty_done, 0);
        if (reservedQuantity > 0) {
            return doneQuantity / reservedQuantity;
        }
        return doneQuantity > 0 ? 1 : 0;
    }

    get packageLabel() {
        if (this.line.isPackageLine && this.line.package_id.parent_package_id) {
            // Need to recompute the result package "complete_name" since it is not recomputed when unpack.
            const currentResultFullPackageName = `${this.line.package_id.parent_package_id.name} > ${this.line.result_package_id.name}`;
            if (
                this.line.package_id.complete_name === currentResultFullPackageName &&
                this.line.outermost_result_package_id
            ) {
                return this.line.package_id.parent_package_id.name;
            }
        }
        return super.packageLabel;
    }

    get resultPackageLabel() {
        if (this.line.isPackageLine) {
            if (this.line.outermost_result_package_id) {
                return this.line.outermost_result_package_id.name;
            }
            return this.line.result_package_id.name;
        }
        return super.resultPackageLabel;
    }

    select(ev) {
        ev.stopPropagation();
        this.env.model.selectPackageLine(this.line);
        this.env.model.trigger("update");
    }

    openPackage() {
        let packageIds = [this.line.package_id.id];
        if (this.line.lines) {
            packageIds = Array.from(new Set(this.line.lines.map((line) => line.package_id.id)));
        }
        return this.props.openPackage(packageIds);
    }

    unpack() {
        this.env.model.unpack(this.line.lines);
        this.env.model.trigger("update");
    }
}
