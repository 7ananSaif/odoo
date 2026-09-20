import BarcodeModel from "@stock_barcode/models/barcode_model";
import { BackorderDialog } from "../components/backorder_dialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Deferred } from "@web/core/utils/concurrency";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { markup } from "@odoo/owl";
import { SignatureDialog } from "@web/core/signature/signature_dialog";
import { useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/core/utils/numbers";

export default class BarcodePickingModel extends BarcodeModel {
    constructor(resModel, resId, services) {
        super(resModel, resId, services);
        this.lineModel = "stock.move.line";
        this.showBackOrderDialog = true;
        this.validateMessage = _t("The transfer has been validated");
        this.validateMethod = "button_validate";
        this.deleteLineMethod = "unlink";
        this.validateContext = {
            display_detailed_backorder: true,
            skip_backorder: true,
        };
        this.lastScanned.destLocation = false;
        this.shouldShortenLocationName = true;
        this.actionName = "stock_barcode.stock_barcode_picking_client_action";
        this.backorderModel = "stock.picking";
        this.needSourceConfirmation = {};
        this.ui = useService("ui");
    }

    setData(data) {
        // Picking type's scan restrictions and other barcode's configuration.
        this.config = data.data.config || {};

        super.setData(...arguments);
        this._useReservation = this.initialState.lines.some((line) => !line.picked);
        const { use_create_lots, use_existing_lots } = this.record.picking_type_id || {};
        this.useTrackingNumber = use_create_lots || use_existing_lots;
        if (!this.useScanDestinationLocation) {
            this.config.restrict_scan_dest_location = "no";
        }
        this.lineFormViewId = data.data.line_view_id;
        this.formViewId = data.data.form_view_id;
        this.scrapViewId = data.data.scrap_view_id;
        this.packageKanbanViewId = data.data.package_view_id;
        this.precision = data.data.precision;
    }

    askBeforeNewLinesCreation(product) {
        return (
            this._useReservation &&
            product &&
            !this.currentState.lines.some((line) => line.product_id.id === product.id)
        );
    }

    createNewLine(params) {
        const product = params.fieldsParams.product_id;
        if (
            this.needSourceConfirmation &&
            this.needSourceConfirmation[this.location.id]?.[product.id]
        ) {
            const message = _t(
                "You are about to take the product %(productName)s from the " +
                    "location %(locationName)s but this product isn't reserved in this location.\n" +
                    "Scan the current location to confirm that.",
                { productName: product.display_name, locationName: this.location.display_name }
            );
            this.needSourceConfirmation[this.location.id][product.id] = false;
            this.notification(message, { type: "danger" });
            return false;
        } else if (this.askBeforeNewLinesCreation(product)) {
            const productName = (product.code ? `[${product.code}] ` : "") + product.display_name;
            if (!this.config.barcode_allow_extra_product) {
                // No unreserved product can't be added, display a warning.
                const message = _t(
                    "The product %s should not be picked in this operation.",
                    productName
                );
                this.notification(message, { type: "danger" });
                return false;
            }
            // Unreserved product can be added but a confirmation is needed.
            const body = _t(
                "Scanned product %s is not reserved for this transfer. Are you sure you want to add it?",
                productName
            );
            const confirmationPromise = new Promise((resolve) => {
                this.trigger("playSound");
                this.dialogService.add(ConfirmationDialog, {
                    title: _t("Add extra product?"),
                    body,
                    cancel: () => resolve(false),
                    confirm: async () => {
                        const newLine = await this._createNewLine(params);
                        resolve(newLine);
                    },
                    close: () => resolve(false),
                });
            });
            return confirmationPromise;
        }
        return super.createNewLine(...arguments);
    }

    getDisplayCompletePackageBtn(line) {
        return line.isPackageLine;
    }

    getDisplayIncrementBtn(line) {
        line = (line.product_id.tracking === "lot" && this._getParentLine(line)) || line;
        return !this.getQtyDemand(line) || this.getQtyDone(line) < this.getQtyDemand(line);
    }

    getDisplayIncrementBtnForSerial(line) {
        const lineTrackingNumber = line.lot_id || line.lot_name;
        return (
            !this.useTrackingNumber ||
            (!this.config.restrict_scan_tracking_number &&
                lineTrackingNumber &&
                this.getQtyDone(line) === 0)
        );
    }

    getLineRemainingQuantity(line) {
        const remainingQty = super.getLineRemainingQuantity(...arguments);
        const parentLine =
            (line.product_id.tracking === "lot" && this._getParentLine(line)) || line;
        if (parentLine && this.getQtyDemand(parentLine)) {
            const parentRemainingQty = this.getQtyDemand(parentLine) - this.getQtyDone(parentLine);
            if (parentRemainingQty) {
                return Math.min(Math.max(1, remainingQty), parentRemainingQty);
            }
        }
        return remainingQty;
    }

    getQtyDone(line) {
        return line.qty_done;
    }

    getQtyDemand(line) {
        return line.reserved_uom_qty || 0;
    }

    getEditedLineParams(line) {
        this._setUser();
        return super.getEditedLineParams(...arguments);
    }

    completePackage(virtualId) {
        this.actionMutex.exec(() => {
            const packageLine = this.packageLines.find((l) => l.virtual_id === virtualId);
            const factor = packageLine.qty_done ? -1 : 1;
            for (const line of packageLine.lines) {
                this.selectedLineVirtualId = line.virtual_id;
                const lineQty = line.reserved_uom_qty || line.qty_done || line.packedQuantity;
                this._updateLineQty(line, { qty_done: lineQty * factor });
                this._markLineAsDirty(line);
            }
            this.trigger("update");
        });
    }

    displayLineQtyDemand(line) {
        if (line.isPackageLine && line.reservedPackage) {
            return true;
        } else if (!this.showReservedSns) {
            return (
                this.getQtyDemand(line) &&
                !(this.lineIsTracked(line) && !line.lines && this._getParentLine(line))
            );
        }
        return super.displayLineQtyDemand(line);
    }

    groupKey(line) {
        return super.groupKey(...arguments) + `_${line.location_dest_id.id}`;
    }

    lineCanBeSelected(line) {
        if (this.selectedLine && this.selectedLine.virtual_id === line.virtual_id) {
            return true; // We consider an already selected line can always be re-selected.
        }
        if (
            this.config.restrict_scan_source_location &&
            !this.lastScanned.sourceLocation &&
            !line.qty_done
        ) {
            return false; // Can't select a line if source is mandatory and wasn't scanned yet.
        }
        if (line.isPackageLine) {
            // The next conditions concern product, skips them in case of package line.
            return super.lineCanBeSelected(...arguments);
        }
        const product = line.product_id;
        if (
            this.config.restrict_put_in_pack === "mandatory" &&
            this.selectedLine &&
            this.selectedLine.qty_done &&
            !this.selectedLine.result_package_id &&
            this.selectedLine.product_id.id != product.id
        ) {
            return false; // Can't select another product if a package must be scanned first.
        }
        if (this.config.restrict_scan_product && product.barcode) {
            // If the product scan is mandatory, a line can't be selected if its product isn't
            // scanned first (as we can't keep track of each line's product scanned state, we
            // consider a product was scanned if the line has a qty. greater than zero).
            if (product.tracking === "none" || !this.config.restrict_scan_tracking_number) {
                return (
                    !this.getQtyDemand(line) ||
                    this.getQtyDone(line) ||
                    (this.lastScanned.product && this.lastScanned.product.id === line.product_id.id)
                );
            } else if (product.tracking != "none") {
                return line.lot_name || (line.lot_id && line.qty_done);
            }
        }
        return super.lineCanBeSelected(...arguments);
    }

    lineCanBeEdited(line) {
        if (
            this.config.restrict_scan_product &&
            line.product_id.barcode &&
            !this.getQtyDone(line) &&
            (!this.lastScanned.product || this.lastScanned.product.id != line.product_id.id)
        ) {
            return false;
        }
        if (
            line.product_id.tracking !== "none" &&
            this.config.restrict_scan_tracking_number &&
            !((line.lot_id && line.qty_done) || line.lot_name)
        ) {
            return false;
        }
        return this.lineCanBeSelected(line);
    }

    lineCanBeTakenFromTheCurrentLocation(line) {
        // A line with no qty. done can be taken regardless its location (it will be overridden).
        const res =
            !this.getQtyDone(line) || super.lineCanBeTakenFromTheCurrentLocation(...arguments);
        // If source location's scan is mandatory, the source should be confirmed (scanned once
        // again) to confirm we want to take this product from the current location.
        if (
            res &&
            this.config.restrict_scan_source_location &&
            line.location_id.id !== this.location.id &&
            this.lineIsReserved(line)
        ) {
            if (this.needSourceConfirmation[this.location.id] === undefined) {
                this.needSourceConfirmation[this.location.id] = {};
            }
            if (
                !this.scanHistory[1].location ||
                this.scanHistory[1].location.id !== this.location.id
            ) {
                this.needSourceConfirmation[this.location.id][line.product_id.id] = true;
                return false;
            }
            // The source was scanned just before, no need to confirm it for this product anymore.
            this.needSourceConfirmation[this.location.id][line.product_id.id] = false;
        }
        return res;
    }

    lineIsReserved(line) {
        return !line.picked && line.quantity;
    }

    async updateLine(line, args) {
        await super.updateLine(...arguments);
        let { location_id, location_dest_id, is_entire_pack } = args;
        if ("result_package_id" in args) {
            let resultPackage = args.result_package_id;
            if (typeof resultPackage === "number") {
                resultPackage = this.cache.getRecord("stock.package", resultPackage);
            }
            if (
                resultPackage.package_type_id &&
                typeof resultPackage.package_type_id === "number"
            ) {
                resultPackage.package_type_id = this.cache.getRecord(
                    "stock.package.type",
                    resultPackage.package_type_id
                );
            }
            line.result_package_id = resultPackage;
        }
        if ("outermost_result_package_id" in args) {
            let outermostResultPackage = args.outermost_result_package_id;
            if (typeof outermostResultPackage === "number") {
                outermostResultPackage = this.cache.getRecord(
                    "stock.package",
                    outermostResultPackage
                );
            }
            line.outermost_result_package_id = outermostResultPackage;
        }
        if (!args.dontUpdateSourceLocation && !location_id && this.lastScanned.sourceLocation) {
            line.location_id = this.lastScanned.sourceLocation;
            if (line.package_id && line.package_id.location_id != line.location_id.id) {
                line.package_id = false;
            }
        }
        if (location_dest_id) {
            if (typeof location_dest_id === "number") {
                location_dest_id = this.cache.getRecord("stock.location", args.location_dest_id);
            }
            line.location_dest_id = location_dest_id;
        }
        if (is_entire_pack) {
            line.is_entire_pack = is_entire_pack;
        }
    }

    updateLineQty(virtualId, qty = 1) {
        this.actionMutex.exec(() => {
            const line = this.pageLines.find((l) => l.virtual_id === virtualId);
            this.updateLine(line, { qty_done: qty });
            this.trigger("update");
        });
    }

    get backordersDomain() {
        return [["backorder_id", "=", this.resId]];
    }

    get barcodeInfo() {
        if (this.isCancelled || this.isDone) {
            return {
                class: this.isDone ? "picking_already_done" : "picking_already_cancelled",
                message: this.isDone
                    ? _t("This picking is already done")
                    : _t("This picking is cancelled"),
                icon: "exclamation-triangle",
                warning: true,
            };
        }
        // Takes the parent line if the current line is part of a group.
        const parentLine = this._getParentLine(this.selectedLine);
        const line = parentLine && this.getQtyDemand(parentLine) ? parentLine : this.selectedLine;
        // Defines some messages who can appear in multiple cases.
        const infos = {
            scanScrLoc: {
                message:
                    this.considerPackageLines && !this.config.restrict_scan_source_location
                        ? _t("Scan the source location or a package")
                        : _t("Scan the source location"),
                class: "scan_src",
                icon: "sign-out",
            },
            scanDestLoc: {
                message: _t("Scan the destination location"),
                class: "scan_dest",
                icon: "sign-in",
            },
            scanProductOrDestLoc: {
                message: this.considerPackageLines
                    ? _t("Scan a product, a package or the destination location.")
                    : _t("Scan a product or the destination location."),
                class: "scan_product_or_dest",
            },
            scanPackage: {
                message: this._getScanPackageMessage(line),
                class: "scan_package",
                icon: "archive",
            },
            scanLot: {
                message: _t("Scan a lot number"),
                class: "scan_lot",
                icon: "barcode",
            },
            scanSerial: {
                message: _t("Scan a serial number"),
                class: "scan_serial",
                icon: "barcode",
            },
            pressValidateBtn: {
                message: _t("Press Validate or scan another product"),
                class: "scan_validate",
                icon: "check-square",
            },
        };
        let barcodeInfo = {
            message: _t("Scan a product"),
            class: "scan_product",
            icon: "tags",
        };
        if ((line || this.lastScanned.packageId) && this.groups.group_stock_multi_locations) {
            if (this.record.picking_type_code === "outgoing" && this.useScanSourceLocation) {
                barcodeInfo = {
                    message: _t("Scan more products, or scan a new source location"),
                    class: "scan_product_or_src",
                };
            } else if (this.config.restrict_scan_dest_location != "no") {
                barcodeInfo = infos.scanProductOrDestLoc;
            }
        }

        if (!line && this._moveEntirePackage()) {
            // About package lines.
            const packageLine = this.selectedPackageLine;
            if (packageLine) {
                if (this._lineIsComplete(packageLine)) {
                    if (
                        this.config.restrict_scan_source_location &&
                        !this.lastScanned.sourceLocation
                    ) {
                        return infos.scanScrLoc;
                    } else if (
                        this.config.restrict_scan_dest_location != "no" &&
                        !this.lastScanned.destLocation
                    ) {
                        return this.config.restrict_scan_dest_location == "mandatory"
                            ? infos.scanDestLoc
                            : infos.scanProductOrDestLoc;
                    } else if (this.pageIsDone) {
                        return infos.pressValidateBtn;
                    } else {
                        barcodeInfo.message = _t("Scan a product or another package");
                        barcodeInfo.class = "scan_product_or_package";
                    }
                } else {
                    barcodeInfo.message = _t(
                        "Scan the package %s",
                        packageLine.result_package_id.name
                    );
                    barcodeInfo.icon = "archive";
                }
                return barcodeInfo;
            } else if (this.considerPackageLines && barcodeInfo.class == "scan_product") {
                barcodeInfo.message = _t("Scan a product or a package");
                barcodeInfo.class = "scan_product_or_package";
            }
        }
        if (
            barcodeInfo.class === "scan_product" &&
            !(line || this.lastScanned.packageId) &&
            this.config.restrict_scan_source_location &&
            this.lastScanned.sourceLocation
        ) {
            barcodeInfo.message = _t(
                "Scan a product from %s",
                this.lastScanned.sourceLocation.name
            );
        }

        // About source location.
        if (this.useScanSourceLocation) {
            if (!this.lastScanned.sourceLocation && !this.pageIsDone) {
                return infos.scanScrLoc;
            } else if (
                this.lastScanned.sourceLocation &&
                this.lastScanned.destLocation == "no" &&
                line &&
                this._lineIsComplete(line)
            ) {
                if (this.config.restrict_put_in_pack === "mandatory" && !line.result_package_id) {
                    return {
                        message: _t("Scan a package"),
                        class: "scan_package",
                        icon: "archive",
                    };
                }
                return infos.scanScrLoc;
            }
        }

        if (!line) {
            if (this.pageIsDone) {
                // All is done, says to validate the transfer.
                return infos.pressValidateBtn;
            } else if (this.config.lines_need_to_be_packed) {
                const lines = new Array(...this.pageLines, ...this.packageLines);
                if (
                    lines.every((line) => !this._lineIsNotComplete(line)) &&
                    lines.some((line) => this._lineNeedsToBePacked(line))
                ) {
                    return infos.scanPackage;
                }
            }
            return barcodeInfo;
        }
        const product = line.product_id;

        // About tracking numbers.
        if (
            product.tracking !== "none" &&
            (this.record.picking_type_id.use_create_lots ||
                this.record.picking_type_id.use_existing_lots)
        ) {
            const isLot = product.tracking === "lot";
            if (this.getQtyDemand(line) && (line.lot_id || line.lot_name)) {
                // Reserved.
                if (this.getQtyDone(line) === 0) {
                    // Lot/SN not scanned yet.
                    return isLot ? infos.scanLot : infos.scanSerial;
                } else if (this.getQtyDone(line) < this.getQtyDemand(line)) {
                    // Lot/SN scanned but not enough.
                    barcodeInfo = isLot ? infos.scanLot : infos.scanSerial;
                    barcodeInfo.message = isLot
                        ? _t("Scan more lot numbers")
                        : _t("Scan another serial number");
                    return barcodeInfo;
                }
            } else if (!(line.lot_id || line.lot_name)) {
                // Not reserved.
                return isLot ? infos.scanLot : infos.scanSerial;
            }
        }

        // About package.
        if (this._lineNeedsToBePacked(line)) {
            if (this._lineIsComplete(line)) {
                return infos.scanPackage;
            }
            if (product.tracking == "serial") {
                barcodeInfo.message = _t("Scan a serial number or a package");
            } else if (product.tracking == "lot") {
                barcodeInfo.message =
                    line.qty_done == 0
                        ? _t("Scan a lot number")
                        : _t("Scan more lot numbers or a package");
                barcodeInfo.class = "scan_lot";
            } else {
                barcodeInfo.message = _t("Scan more products or a package");
            }
            return barcodeInfo;
        }

        if (this.pageIsDone) {
            barcodeInfo = infos.pressValidateBtn;
        }

        // About destination location.
        const lineWaitingPackage =
            this.groups.group_tracking_lot &&
            this.config.restrict_put_in_pack != "no" &&
            !line.result_package_id;
        if (this.config.restrict_scan_dest_location != "no" && line.qty_done) {
            if (this.pageIsDone) {
                if (this.lastScanned.destLocation) {
                    return infos.pressValidateBtn;
                } else {
                    return this.config.restrict_scan_dest_location == "mandatory" &&
                        this._lineIsComplete(line)
                        ? infos.scanDestLoc
                        : infos.scanProductOrDestLoc;
                }
            } else if (this._lineIsComplete(line)) {
                if (lineWaitingPackage) {
                    barcodeInfo.message =
                        this.config.restrict_scan_dest_location == "mandatory"
                            ? _t("Scan a package or the destination location")
                            : _t("Scan a package, the destination location or another product");
                } else {
                    return this.config.restrict_scan_dest_location == "mandatory"
                        ? infos.scanDestLoc
                        : infos.scanProductOrDestLoc;
                }
            } else {
                barcodeInfo = infos.scanProductOrDestLoc;
                if (product.tracking == "serial") {
                    barcodeInfo.message = lineWaitingPackage
                        ? _t("Scan a serial number or a package then the destination location")
                        : _t("Scan a serial number then the destination location");
                } else if (product.tracking == "lot") {
                    barcodeInfo.message = lineWaitingPackage
                        ? _t("Scan a lot number or a packages then the destination location")
                        : _t("Scan a lot number then the destination location");
                } else {
                    barcodeInfo.message = lineWaitingPackage
                        ? _t("Scan a product, a package or the destination location")
                        : _t("Scan a product then the destination location");
                }
            }
        }

        return barcodeInfo;
    }

    get canBeProcessed() {
        return !["cancel", "done"].includes(this.record.state);
    }

    get displaySignatureButton() {
        return (
            this.record.picking_type_code === "outgoing" &&
            !this.record.signature &&
            this.groups.group_stock_sign_delivery
        );
    }

    /**
     * Depending of the config, a transfer can be fully validate even if nothing was scanned (like
     * with an immediate transfer) or if at least one product was scanned.
     * @returns {boolean}
     */
    get canBeValidate() {
        if (!this._useReservation) {
            return super.canBeValidate; // For immediate transfers, doesn't care about any special condition.
        } else if (
            !this.config.barcode_validation_full &&
            !this.currentState.lines.some((line) => line.qty_done)
        ) {
            return false; // Can't be validate because "full validation" is forbidden and nothing was processed yet.
        }
        return super.canBeValidate;
    }

    get cancelLabel() {
        return _t("Cancel Transfer");
    }

    get canCreateNewLot() {
        return this.record.use_create_lots;
    }

    get showReservedSns() {
        if (this.canCreateNewLot && !this.useExistingLots) {
            return false;
        }
        return this.record.picking_type_id.show_reserved_sns;
    }

    get canPutInPack() {
        if (this.config.restrict_scan_product) {
            return this.pageLines.some((line) => line.qty_done && !line.result_package_id);
        }
        return true;
    }

    get canScrap() {
        const { picking_type_code, state } = this.record;
        return (
            (picking_type_code === "incoming" && state === "done") ||
            (picking_type_code === "outgoing" && state !== "done") ||
            picking_type_code === "internal"
        );
    }

    get scrapContext() {
        const context = this._getNewLineDefaultContext();
        delete context.force_fullfil_quantity;
        const moves = this.record.move_ids.map((id) => this.cache.getRecord("stock.move", id));
        context["product_ids"] = moves.map((move) => move.product_id);
        return context;
    }

    get canSelectLocation() {
        return !(
            this.config.restrict_scan_source_location ||
            this.config.restrict_scan_dest_location != "optional"
        );
    }

    shouldSplitLine(line) {
        if (!line.qty_done || !line.reserved_uom_qty || line.qty_done >= line.reserved_uom_qty) {
            return false; // No need to split a completed line or a line with no reservation.
        }
        line = this._getParentLine(line) || line;
        return line.qty_done && line.reserved_uom_qty && line.qty_done < line.reserved_uom_qty;
    }

    /**
     * Splits a line if its qty done is less than reserved.
     * In case of a grouped line, if there's is a lot id or product tracking is serial,
     * the new line doesn't need to be splitted since there is an existing line
     * that will be grouped seperately after location is changed.
     *
     * @returns {Boolean|Object} Returns the new splitted line or false if line can't be split.
     */
    async splitLine(line) {
        if (!this.shouldSplitLine(line)) {
            return false;
        }
        // Use line's locations otherwise the picking's locations are used as default locations.
        const fieldsParams = {
            location_id: line.location_id.id,
            location_dest_id: line.location_dest_id.id,
            package_id: line.package_id?.id,
            picking_id: line.picking_id,
        };
        const newLine = await this._createNewLine({ copyOf: line, fieldsParams });
        delete newLine.parentLine;
        // Update the reservation of the both old and new lines.
        newLine.reserved_uom_qty = line.reserved_uom_qty - line.qty_done;
        line.reserved_uom_qty = line.qty_done;
        // Be sure the new line has no lot by default.
        newLine.lot_id = false;
        newLine.lot_name = false;

        return newLine;
    }

    /**
     * The line's destination is changed to the given location, and if the line's reservation isn't
     * fulfilled, the remaining qties are moved to a new line with the original destination location.
     *
     * @param {int} id location's id
     */
    async changeDestinationLocation(id, selectedLine) {
        if (selectedLine.lines && !selectedLine.isPackageLine) {
            this._clearScanData();
            return false;
        }
        if (!selectedLine.lot_id) {
            await this.splitLine(selectedLine);
        }
        // If the line has no reservation and is grouped with sibling lines,
        // checks if we can assign to it a part of the reservation.
        const parentLine = this._getParentLine(selectedLine);
        if (
            selectedLine.product_id.tracking === "lot" &&
            parentLine &&
            selectedLine.qty_done &&
            !selectedLine.reserved_uom_qty
        ) {
            // Searches for a line with uncomplete reservation.
            const uncompletedLine = parentLine.lines.find(
                (line) => line.reserved_uom_qty && line.qty_done < line.reserved_uom_qty
            );
            if (uncompletedLine) {
                // Checks if a portion of the reservation can be assign to the current line.
                const remainingQty = Math.max(
                    0,
                    uncompletedLine.reserved_uom_qty - uncompletedLine.qty_done
                );
                const stolenReservation = Math.min(remainingQty, selectedLine.qty_done);
                if (stolenReservation) {
                    // Assigns the reservation on the current line.
                    uncompletedLine.reserved_uom_qty -= stolenReservation;
                    selectedLine.reserved_uom_qty = stolenReservation;
                }
            }
        }
        selectedLine.location_dest_id = this.cache.getRecord("stock.location", id);
        this._markLineAsDirty(selectedLine);
        this._clearScanData();
        return true;
    }

    _clearScanData() {
        this.selectedLineVirtualId = false;
        this.location = false;
        this.lastScanned.packageId = false;
        this.lastScanned.product = false;
        this.scannedLinesVirtualId = [];
    }

    get considerPackageLines() {
        return this._moveEntirePackage() && this.packageLines.length;
    }

    get displayAddProductButton() {
        return !this._useReservation || this.config.barcode_allow_extra_product;
    }

    get displayCancelButton() {
        return !["done", "cancel"].includes(this.record.state);
    }

    get displayDestinationLocation() {
        return (
            this.groups.group_stock_multi_locations &&
            ["incoming", "internal"].includes(this.record.picking_type_code)
        );
    }

    get displayPutInPackButton() {
        return this.groups.group_tracking_lot && this.config.restrict_put_in_pack != "no";
    }

    get displayResultPackage() {
        return true;
    }

    get displaySourceLocation() {
        return (
            super.displaySourceLocation &&
            ["internal", "outgoing"].includes(this.record.picking_type_code)
        );
    }

    get displayReturnButton() {
        return this.resModel === "stock.picking" && this.isDone;
    }

    get useScanSourceLocation() {
        return super.useScanSourceLocation && this.config.restrict_scan_source_location;
    }

    get useScanDestinationLocation() {
        return super.useScanDestinationLocation && this.config.restrict_scan_dest_location != "no";
    }

    get displayValidateButton() {
        return true;
    }

    get highlightValidateButton() {
        if (!this.pageLines.length && !this.packageLines.length) {
            return false;
        }
        if (
            this.config.lines_need_destination_location &&
            !this.lastScanned.destLocation &&
            (this.selectedLine || this.lastScanned.packageId)
        ) {
            return false;
        }
        for (let line of this.pageLines) {
            line = this._getParentLine(line) || line;
            if (this._lineIsNotComplete(line)) {
                return false;
            }
        }
        for (const packageLine of this.packageLines) {
            if (this._lineIsNotComplete(packageLine)) {
                return false;
            }
        }
        return Boolean([...this.pageLines, ...this.packageLines].length);
    }

    get isDone() {
        return this.record.state === "done";
    }

    get isCancelled() {
        return this.record.state === "cancel";
    }

    lineIsFaulty(line) {
        return (
            this._useReservation &&
            line.qty_done > line.reserved_uom_qty &&
            (this.showReservedSns || !this.lineIsTracked(line))
        );
    }

    get moveIds() {
        return this.record.move_ids;
    }

    get packageLines() {
        if (!this._moveEntirePackage() || !this.currentState.lines.length) {
            return [];
        }
        return this._getPackageLines();
    }

    get pageIsDone() {
        for (const line of this.groupedLines) {
            if (
                this._lineIsNotComplete(line) ||
                this._lineNeedsToBePacked(line) ||
                (line.product_id.tracking != "none" && !(line.lot_id || line.lot_name))
            ) {
                return false;
            }
        }
        for (const line of this.packageLines) {
            if (this._lineIsNotComplete(line)) {
                return false;
            }
        }
        return Boolean([...this.groupedLines, ...this.packageLines].length);
    }

    /**
     * Returns only the lines.
     * @returns {Array<Object>}
     */
    get pageLines() {
        let lines = super.pageLines;
        if (this._moveEntirePackage()) {
            lines = lines.filter(
                (line) => !(line.package_id && line.result_package_id && line.is_entire_pack)
            );
        }
        return this._sortLine(lines);
    }

    get previousScannedLinesByPackage() {
        if (this.lastScanned.packageId) {
            return this.currentState.lines.filter(
                (l) => l.result_package_id.id === this.lastScanned.packageId
            );
        }
        return [];
    }

    get printButtons() {
        const buttons = [
            {
                name: _t("Print Picking Operations"),
                class: "o_print_picking",
                method: "do_print_picking",
            },
            {
                name: _t("Print Delivery Slip"),
                class: "o_print_delivery_slip",
                method: "action_print_delivery_slip",
            },
            {
                name: _t("Print Barcodes"),
                class: "o_print_barcodes",
                method: "action_print_barcode",
            },
        ];
        if (this.groups.group_tracking_lot) {
            buttons.push({
                name: _t("Print Packages"),
                class: "o_print_packages",
                method: "action_print_packges",
            });
        }

        return buttons;
    }

    get reloadingMoveLines() {
        return this.currentState !== undefined;
    }

    async save() {
        if (this.linesToSave.length > 0) {
            await this._setUser();
        }
        return super.save();
    }

    /**
     * Return the last scanned package line (only relevant for "move entire package" operations.)
     */
    get selectedPackageLine() {
        return (
            this.lastScanned.packageId &&
            this.packageLines.find((pl) => pl.result_package_id.id == this.lastScanned.packageId)
        );
    }

    /**
     * Return previously scanned packages.
     */
    get lastScannedPackages() {
        const packages = [];
        for (let barcodeIndex = 0; barcodeIndex < this.scanHistory.length; barcodeIndex++) {
            const barcodeData = this.scanHistory[barcodeIndex];
            if (barcodeData.package) {
                packages.push(barcodeData.package);
            } else if (barcodeData.packageType && barcodeIndex === 0) {
                // Special case: if the last scanned barcode is a package type,
                // we skip it without breaking the loop because it can mean we want
                // to put in pack scanned package(s) into a new package of this type.
                continue;
            } else {
                break;
            }
        }
        return packages;
    }

    get useExistingLots() {
        return this.record.use_existing_lots;
    }

    async uploadSignature({ signatureImage }) {
        const file = signatureImage.split(",")[1];

        this.ui.block();
        await this.orm.write(this.resModel, [this.resId], {
            signature: file,
        });
        this.ui.unblock();
        await this.save();
        this.trigger("refresh");
    }

    openSignatureDialog(validateAfterSignature = false) {
        const nameAndSignatureProps = {
            mode: "draw",
            displaySignatureRatio: 3,
            signatureType: "signature",
            noInputName: true,
        };
        const defaultName = this.record.partner_id?.display_name;

        const dialogProps = {
            defaultName,
            nameAndSignatureProps,
            uploadSignature: async (data) => {
                await this.uploadSignature(data);
                if (validateAfterSignature) {
                    await super.validate();
                }
            },
        };
        this.dialogService.add(SignatureDialog, dialogProps);
    }

    get shouldOpenSignatureModal() {
        const { picking_type_code: pickingTypeCode, signature } = this.record;
        return (
            pickingTypeCode === "outgoing" && !signature && this.groups.group_stock_sign_delivery
        );
    }

    async validate() {
        if (
            this.config.lines_need_destination_location &&
            !this.lastScanned.destLocation &&
            (this.selectedLine || this.lastScanned.packageId)
        ) {
            return this.notification(_t("Destination location must be scanned"), {
                type: "danger",
            });
        }
        if (
            this.config.lines_need_to_be_packed &&
            this.currentState.lines.some((line) => this._lineNeedsToBePacked(line))
        ) {
            return this.notification(_t("All products need to be packed"), { type: "danger" });
        }
        await this._setUser();
        if (this.config.create_backorder === "ask") {
            // If there are some uncompleted lines, displays the backorder dialog.
            const uncompletedLines = [];
            const alreadyChecked = [];
            let atLeastOneLinePartiallyProcessed = false;
            for (let line of this.currentState.lines) {
                line = this._getParentLine(line) || line;
                if (alreadyChecked.includes(line.virtual_id)) {
                    continue;
                }
                // Keeps track of already checked lines to avoid to check multiple times grouped lines.
                alreadyChecked.push(line.virtual_id);
                let qtyDone = line.qty_done;
                if (qtyDone < line.reserved_uom_qty) {
                    // Checks if another move line shares the same move id and adds its quantity done in that case.
                    qtyDone += this.currentState.lines.reduce(
                        (additionalQtyDone, otherLine) =>
                            otherLine.product_id.id === line.product_id.id &&
                            otherLine.move_id === line.move_id &&
                            !otherLine.reserved_uom_qty
                                ? additionalQtyDone + otherLine.qty_done
                                : additionalQtyDone,
                        0
                    );
                    if (qtyDone < line.reserved_uom_qty) {
                        // Quantity done still insufficient.
                        uncompletedLines.push(line);
                    }
                }
                atLeastOneLinePartiallyProcessed = atLeastOneLinePartiallyProcessed || qtyDone > 0;
            }
            if (
                this.showBackOrderDialog &&
                atLeastOneLinePartiallyProcessed &&
                uncompletedLines.length
            ) {
                this.trigger("playSound");
                return this.dialogService.add(BackorderDialog, {
                    displayUoM: this.groups.group_uom,
                    uncompletedLines,
                    onApply: () => super.validate(),
                });
            }
        }
        if (this.record.return_id) {
            this.validateContext = {
                ...this.validateContext,
                picking_ids_not_to_backorder: this.resId,
            };
        }
        if (this.shouldOpenSignatureModal) {
            this.openSignatureDialog(true);
            return;
        }
        return await super.validate();
    }

    // -------------------------------------------------------------------------
    // Private
    // -------------------------------------------------------------------------

    async _assignEmptyPackage(line, resultPackage) {
        const fieldsParams = this._convertDataToFieldsParams({ resultPackage });
        fieldsParams.dontUpdateSourceLocation = true;
        const parentLine = this._getParentLine(line);
        const targetLines = parentLine ? parentLine.lines : [line];
        for (const subline of targetLines) {
            // Assigns the result package on all sibling lines
            if (subline === line || (subline.qty_done && !subline.result_package_id)) {
                if (this.shouldSplitLine(subline)) {
                    // Subline has no package already and is only partially full,
                    // so we split off the remaining amount into a new move line
                    const newLine = await this.splitLine(subline);
                    [newLine.sortIndex, subline.sortIndex] = [subline.sortIndex, newLine.sortIndex];
                    if (subline === line) {
                        this.selectLine(newLine);
                    }
                }
                await this.updateLine(subline, fieldsParams);
            }
        }
    }

    _getNewLineDefaultContext() {
        return {
            default_company_id: this.record.company_id,
            default_location_id: this.lastScanned.sourceLocation.id || this._defaultLocation().id,
            default_location_dest_id: this._defaultDestLocation().id,
            default_picking_id: this.resId,
            default_qty_done: 1,
            display_default_code: false,
            hide_unlink_button: Boolean(!this.selectedLine || this.selectedLine.reserved_uom_qty),
            force_fullfil_quantity: this.selectedLine && this.selectedLine.reserved_uom_qty,
        };
    }

    async _cancel() {
        await this.save();
        await this.orm.call(this.resModel, "action_cancel", [[this.resId]]);
        this._cancelNotification();
        this.trigger("history-back");
    }

    _cancelNotification() {
        this.notification(_t("The transfer has been cancelled"));
    }

    _checkBarcode(barcodeData) {
        const check = { title: _t("Not the expected scan") };
        const { location, lot, product, destLocation, packageType } = barcodeData;
        const resultPackage = barcodeData.package;

        if (this.config.restrict_scan_source_location && !barcodeData.location) {
            // Special case where the user can not scan a destination but a source was already scanned.
            // That means what is supposed to be a destination is in this case a source.
            if (
                this.lastScanned.sourceLocation &&
                barcodeData.destLocation &&
                this.config.restrict_scan_dest_location == "no"
            ) {
                barcodeData.location = barcodeData.destLocation;
                delete barcodeData.destLocation;
            }
            // Special case where the source is mandatory and the app's waiting for but none was
            // scanned, get the previous scanned one if possible.
            if (!this.lastScanned.sourceLocation && this._currentLocation) {
                this.lastScanned.sourceLocation = this._currentLocation;
            }
        }

        if (
            this.config.restrict_scan_source_location &&
            !this._currentLocation &&
            !this.selectedLine
        ) {
            // Source Location.
            if (!location) {
                check.title = _t("Mandatory Source Location");
                check.message = _t(
                    "You are supposed to scan %s or another source location",
                    this.location.display_name
                );
            }
        } else if (this._mustScanProductFirst(barcodeData)) {
            check.message = lot
                ? _t("Scan a product before scanning a tracking number")
                : _t("You must scan a product");
        } else if (
            this.config.restrict_put_in_pack == "mandatory" &&
            !(resultPackage || packageType) &&
            this.selectedLine &&
            !this.qty_done &&
            !this.selectedLine.result_package_id &&
            ((product && product.id != this.selectedLine.product_id.id) || location || destLocation)
        ) {
            // Package.
            check.message = _t("You must scan a package or put in pack");
        } else if (
            this.config.restrict_scan_dest_location == "mandatory" &&
            !this.lastScanned.destLocation
        ) {
            // Destination Location.
            if (destLocation) {
                this.lastScanned.destLocation = destLocation;
            } else if (
                product &&
                this.selectedLine &&
                this.selectedLine.product_id.id != product.id
            ) {
                // Cannot scan another product before a destination was scanned.
                check.title = _t("Mandatory Destination Location");
                check.message = _t(
                    "Please scan destination location for %s before scanning other product",
                    this.selectedLine.product_id.display_name
                );
            }
        }
        check.error = Boolean(check.message);
        return check;
    }

    _mustScanProductFirst(barcodeData) {
        const { location, product } = barcodeData;
        const packageWithQuant = barcodeData.package?.contained_quant_ids?.length;
        return (
            this.config.restrict_scan_product && // Restriction on product.
            !(product || packageWithQuant || this.selectedLine) && // A product/package was scanned.
            !(this.config.restrict_scan_source_location && location && !this.selectedLine) // Maybe the user scanned the wrong location and trying to scan the right one
        );
    }

    async _closeValidate(ev) {
        const record = await this.orm.read(this.resModel, [this.record.id], ["state"]);
        if (record[0].state === "done") {
            // Checks if the picking generated a backorder. Updates the picking's data if it's the case.
            const backorders = await this.orm.searchRead(
                this.backorderModel,
                this.backordersDomain,
                ["display_name", "id"]
            );
            const buttons = backorders.map((bo) => {
                const additionalContext = { active_id: bo.id };
                return {
                    name: bo.display_name,
                    onClick: () => {
                        this.action.doAction(this.actionName, { additionalContext });
                    },
                };
            });
            if (backorders.length) {
                const phrase =
                    backorders.length === 1
                        ? _t("Following backorder was created:")
                        : _t("Following backorders were created:");
                this.validateMessage = markup`<div>
                    <p>${this.validateMessage}<br>${phrase}</p>
                </div>`;
            }
            // If all is OK, displays a notification and goes back to the previous page.
            this.notification(this.validateMessage, { type: "success", buttons });
            this.trigger("history-back");
        }
    }

    _convertDataToFieldsParams(args) {
        const params = {
            lot_name: args.lotName,
            product_id: args.product,
            qty_done: args.quantity,
        };
        if (args.lot) {
            params.lot_id = args.lot;
        }
        if (args.package) {
            params.package_id = args.package;
        }
        if (
            args.packaging &&
            args.product.tracking === "serial" &&
            (this.useExistingLots || this.canCreateNewLot)
        ) {
            params.packaging = args.packaging;
            params.qty_done = 0;
        }
        if (args.resultPackage) {
            params.result_package_id = args.resultPackage;
        }
        if (args.owner) {
            params.owner_id = args.owner;
        }
        if (args.destLocation) {
            params.location_dest_id = args.destLocation.id;
        }
        if (args.srcLocation) {
            params.location_id = args.srcLocation;
        }
        if (args.isEntirePack) {
            params.is_entire_pack = args.isEntirePack;
        }
        return params;
    }

    _createCommandVals(line) {
        const values = {
            dummy_id: line.virtual_id,
            is_entire_pack: line.is_entire_pack,
            location_id: line.location_id,
            location_dest_id: line.location_dest_id,
            lot_name: line.lot_name,
            lot_id: line.lot_id,
            package_id: line.package_id,
            picking_id: line.picking_id,
            picked: true,
            product_id: line.product_id,
            product_uom_id: line.product_uom_id,
            owner_id: line.owner_id,
            quantity: line.qty_done,
            result_package_id: line.result_package_id,
            state: "assigned",
        };
        for (const [key, value] of Object.entries(values)) {
            values[key] = this._fieldToValue(value);
        }
        return values;
    }

    _getMoveLineData(id) {
        const smlData = this.cache.getRecord("stock.move.line", id);
        smlData.dummy_id = smlData.dummy_id && Number(smlData.dummy_id);
        // Checks if this line is already in the picking's state to get back
        // its `virtual_id` (and so, avoid to set a new `virtual_id`).
        let prevLine = this.currentState?.lines.find((line) => line.id === id);
        if (!prevLine && smlData.dummy_id) {
            prevLine = this.currentState?.lines.find(
                (line) => line.virtual_id === smlData.dummy_id
            );
        }
        const previousVirtualId = prevLine && prevLine.virtual_id;
        smlData.virtual_id = smlData.dummy_id || previousVirtualId || this._uniqueVirtualId;
        smlData.product_id = this.cache.getRecord("product.product", smlData.product_id);
        smlData.product_uom_id = this.cache.getRecord("uom.uom", smlData.product_uom_id);
        smlData.packaging_uom_id =
            smlData.packaging_uom_id && this.cache.getRecord("uom.uom", smlData.packaging_uom_id);
        smlData.location_id = this.cache.getRecord("stock.location", smlData.location_id);
        smlData.location_dest_id = this.cache.getRecord("stock.location", smlData.location_dest_id);
        smlData.lot_id = smlData.lot_id && this.cache.getRecord("stock.lot", smlData.lot_id);
        smlData.owner_id =
            smlData.owner_id && this.cache.getRecord("res.partner", smlData.owner_id);
        smlData.package_id =
            smlData.package_id && this.cache.getRecord("stock.package", smlData.package_id);
        smlData.outermost_result_package_id =
            smlData.outermost_result_package_id &&
            this.cache.getRecord("stock.package", smlData.outermost_result_package_id);

        if (smlData.package_id?.parent_package_id) {
            smlData.package_id.parent_package_id = this.cache.getRecord(
                "stock.package",
                smlData.package_id.parent_package_id
            );
        }

        if (this.reloadingMoveLines) {
            if (prevLine) {
                smlData.sortIndex = prevLine.sortIndex;
                if (smlData.quantity && !smlData.qty_done) {
                    // The reservation likely changed.
                    smlData.reserved_uom_qty = smlData.quantity;
                } else {
                    if (smlData.product_uom_id.id !== prevLine.product_uom_id.id) {
                        // Compatible but not the same UoM => Need a conversion.
                        const params = { digits: [false, this.precision] };
                        const baseQty =
                            (prevLine.reserved_uom_qty * prevLine.product_uom_id.factor) /
                            smlData.product_uom_id.factor;
                        smlData.reserved_uom_qty = parseFloat(formatFloat(baseQty, params));
                    } else {
                        // The reservation of this line is already known.
                        smlData.reserved_uom_qty = prevLine.reserved_uom_qty;
                    }
                }
            } else {
                // This line was created in the Barcode App, so it has no reservation.
                smlData.qty_done = smlData.quantity;
                smlData.reserved_uom_qty = 0;
            }
        } else {
            // First loading: `reserved_uom_qty` keeps in memory what is the
            // initial reservation for this move line clientside only, this
            // information is lost once the user closes the operation.
            smlData.reserved_uom_qty = smlData.quantity;
        }

        const resultPackage =
            smlData.result_package_id &&
            this.cache.getRecord("stock.package", smlData.result_package_id);
        if (resultPackage) {
            // Fetch the package type if needed.
            smlData.result_package_id = resultPackage;
            const packageType = resultPackage && resultPackage.package_type_id;
            resultPackage.package_type_id =
                packageType && this.cache.getRecord("stock.package.type", packageType);
        }
        if (smlData.result_package_id?.parent_package_id) {
            smlData.result_package_id.parent_package_id = this.cache.getRecord(
                "stock.package",
                smlData.result_package_id.parent_package_id
            );
        }
        return smlData;
    }

    _createLinesState() {
        const lines = [];
        const picking = this.cache.getRecord(this.resModel, this.resId);
        for (const id of picking.move_line_ids) {
            const smlData = this._getMoveLineData(id);
            lines.push(smlData);
        }
        return lines;
    }

    _defaultLocation() {
        return this.cache.getRecord("stock.location", this.record.location_id);
    }

    _defaultDestLocation() {
        return this.cache.getRecord("stock.location", this.record.location_dest_id);
    }

    _getCommands() {
        const commands = Object.assign(super._getCommands(), {
            OBTPRSL: this.print.bind(this, false, "action_print_delivery_slip"),
            OBTPROP: this.print.bind(this, false, "do_print_picking"),
            OBTSCRA: this._scrap.bind(this),
            OBTRETU: this._returnProducts.bind(this),
        });
        if (!this.isDone) {
            commands["OBTPACK"] = this._putInPack.bind(this);
            commands["OCDCANC"] = this._cancel.bind(this);
        }
        // Dummy command to avoid error message.
        commands.OBTUPCK = () => {};
        return commands;
    }

    _getDefaultMessageType() {
        if (this.useScanSourceLocation && !this.lastScanned.sourceLocation) {
            return "scan_src";
        }
        return "scan_product";
    }

    _getModelRecord() {
        const record = this.cache.getRecord(this.resModel, this.resId);
        if (record.picking_type_id && record.state !== "cancel") {
            record.picking_type_id = this.cache.getRecord(
                "stock.picking.type",
                record.picking_type_id
            );
        }
        if (record.partner_id && record.state !== "cancel") {
            record.partner_id = this.cache.getRecord("res.partner", record.partner_id);
        }
        return record;
    }

    _getNewLineDefaultValues(fieldsParams) {
        const defaultValues = super._getNewLineDefaultValues(...arguments);
        if (
            this.selectedLine &&
            !fieldsParams.move_id &&
            this.selectedLine.product_id.id === fieldsParams.product_id?.id
        ) {
            defaultValues.move_id = this.selectedLine.move_id;
        }
        const newLineDefaultVals = Object.assign(defaultValues, {
            location_dest_id: this._defaultDestLocation(),
            reserved_uom_qty: 0,
            qty_done: 0,
            picking_id: this.resId,
            result_package_id: false,
            is_entire_pack: false,
        });
        if (fieldsParams.product_id?.tracking === "serial" && fieldsParams.packaging) {
            newLineDefaultVals.reserved_uom_qty = 1;
        }
        return newLineDefaultVals;
    }

    _getFieldToWrite() {
        return [
            "is_entire_pack",
            "location_id",
            "location_dest_id",
            "lot_id",
            "lot_name",
            "package_id",
            "outermost_result_package_id",
            "owner_id",
            "qty_done",
            "result_package_id",
        ];
    }

    _getPackageLines() {
        const linesWithPackage = this.currentState.lines.filter(
            (line) =>
                line.is_entire_pack &&
                line.package_id &&
                line.result_package_id &&
                line.package_id.complete_name === line.result_package_id.complete_name
        );
        // Groups lines by package.
        const groupedLines = {};
        for (const line of linesWithPackage) {
            const packageId =
                line.package_id.outermost_package_id ||
                line.outermost_result_package_id?.id ||
                line.package_id.id;
            if (!groupedLines[packageId]) {
                groupedLines[packageId] = [];
            }
            groupedLines[packageId].push(line);
        }
        const packageLines = [];
        for (const key in groupedLines) {
            // Check if the package is reserved.
            const reservedPackage = groupedLines[key].every((line) => this.lineIsReserved(line));
            groupedLines[key][0].reservedPackage = reservedPackage;
            const packageLine = Object.assign({}, groupedLines[key][0], {
                lines: groupedLines[key],
                isPackageLine: true,
            });
            packageLines.push(packageLine);
        }
        return this._sortLine(packageLines);
    }

    _getSaveCommand() {
        const commands = this._getSaveLineCommand();
        if (commands.length) {
            return {
                route: "/stock_barcode/save_barcode_data",
                params: {
                    model: this.resModel,
                    res_id: this.resId,
                    write_field: "move_line_ids",
                    write_vals: commands,
                },
            };
        }
        return {};
    }

    _getScanPackageMessage() {
        return _t("Scan a package or put in pack");
    }

    _groupSublines() {
        const groupedLine = super._groupSublines(...arguments);
        groupedLine.reserved_uom_qty = groupedLine.totalQtyDemand;
        groupedLine.qty_done = groupedLine.totalQtyDone;
        return groupedLine;
    }

    _incrementTrackedLine() {
        return !(this.record.use_create_lots || this.record.use_existing_lots);
    }

    _lineCannotBeTaken(line) {
        // A packed line without expected quantity or completed cannot be taken
        const fullyPacked =
            line.result_package_id && (!line.reserved_uom_qty || this._lineIsComplete(line));
        return fullyPacked || super._lineCannotBeTaken(...arguments);
    }

    _lineIsComplete(line) {
        const isComplete = line.reserved_uom_qty && line.qty_done >= line.reserved_uom_qty;
        if (line.isPackageLine && !line.reserved_uom_qty && line.qty_done) {
            return true; // For package line, considers an unreserved package as a completed line.
        }
        if (isComplete && line.lines) {
            // Grouped lines/package lines have multiple sublines.
            for (const subline of line.lines) {
                // For tracked product, a line with `qty_done` but no tracking number is considered as not complete.
                if (subline.product_id.tracking != "none") {
                    if (subline.qty_done && !(subline.lot_id || subline.lot_name)) {
                        return false;
                    }
                } else if (
                    subline.reserved_uom_qty &&
                    subline.qty_done < subline.reserved_uom_qty
                ) {
                    return false;
                }
            }
        }
        return isComplete;
    }

    _lineIsNotComplete(line) {
        const currentLine =
            (line.product_id.tracking !== "none" && this._getParentLine(line)) || line;
        let isNotComplete =
            currentLine.reserved_uom_qty && currentLine.qty_done < currentLine.reserved_uom_qty;
        // if we're using the parent line we don't want to return true if the parent line is incomplete but not the line
        if (isNotComplete && line != currentLine) {
            isNotComplete = line.reserved_uom_qty && line.qty_done < line.reserved_uom_qty;
        }
        if (!isNotComplete && currentLine.lines) {
            // Grouped lines/package lines have multiple sublines.
            for (const subline of currentLine.lines) {
                // For tracked product, a line with `qty_done` but no tracking number is considered as not complete.
                if (subline.product_id.tracking != "none") {
                    if (subline.qty_done && !(subline.lot_id || subline.lot_name)) {
                        return true;
                    }
                } else if (
                    subline.reserved_uom_qty &&
                    subline.qty_done < subline.reserved_uom_qty
                ) {
                    return true;
                }
            }
        }
        return isNotComplete;
    }

    _lineNeedsToBePacked(line) {
        return Boolean(
            this.config.lines_need_to_be_packed && line.qty_done && !line.result_package_id
        );
    }

    _moveEntirePackage() {
        return this.record.picking_type_entire_packs;
    }

    async _processBarcode(barcode) {
        if (this.isDone && !this.commands[barcode]) {
            return this.notification(_t("This picking is already done"), { type: "danger" });
        }
        return super._processBarcode(barcode);
    }

    async _processLocation(barcodeData) {
        super._processLocation(...arguments);
        if (barcodeData.destLocation) {
            await this._processLocationDestination(barcodeData);
            this.trigger("update");
        }
    }

    async _processLocationSource(barcodeData) {
        // For planned transfers, check the scanned location is a part of transfer source location.
        if (
            this._useReservation &&
            !this._isSublocation(barcodeData.location, this._defaultLocation())
        ) {
            barcodeData.stopped = true;
            const message = _t("The scanned location doesn't belong to this operation's location");
            return this.notification(message, { type: "danger" });
        }
        super._processLocationSource(...arguments);
        // Splits uncompleted lines to be able to add reserved products from unreserved location.
        let currentLine = this.selectedLine || this.lastScannedLine;
        currentLine = this._getParentLine(currentLine) || currentLine;
        if (currentLine && currentLine.location_id.id !== barcodeData.location.id) {
            const qtyDone = this.getQtyDone(currentLine);
            const reservedQty = this.getQtyDemand(currentLine);
            const remainingQty = reservedQty - qtyDone;
            if (this.shouldSplitLine(currentLine)) {
                const fieldsParams = this._convertDataToFieldsParams(barcodeData);
                let newLine;
                if (currentLine.lines) {
                    for (const line of currentLine.lines) {
                        if (!line.reserved_uom_qty) {
                            line.reserved_uom_qty = line.qty_done;
                        }
                        if (this.shouldSplitLine(line) && !newLine) {
                            newLine = await this._createNewLine({
                                copyOf: line,
                                fieldsParams,
                            });
                            delete newLine.parentLine;
                            line.reserved_uom_qty = line.qty_done;
                        }
                    }
                } else {
                    newLine = await this._createNewLine({
                        copyOf: currentLine,
                        fieldsParams,
                    });
                }
                currentLine.reserved_uom_qty = qtyDone;
                if (newLine) {
                    newLine.reserved_uom_qty = remainingQty;
                    newLine.lot_id = false;
                    this._markLineAsDirty(newLine);
                }
                this._markLineAsDirty(currentLine);
            }
        }
    }

    /**
     * Returns true if the first given location is a sublocation of the second given location.
     * @param {Object} childLocation
     * @param {Object} parentLocation
     * @returns {boolean}
     */
    _isSublocation(childLocation, parentLocation) {
        return childLocation.parent_path.includes(parentLocation.parent_path);
    }

    _getLinesToMove() {
        const configScanDest = this.config.restrict_scan_dest_location;
        // Usually, assign the destination to the selected line or to the selected package's lines.
        let lines = this.selectedPackageLine?.lines || this.selectedLine ? [this.selectedLine] : [];
        if (configScanDest === "mandatory" && this.selectedLine?.product_id?.tracking !== "none") {
            // When we assign the location to only the last scanned line, if the selected line is
            // tracked, we want to assign the destination to its scanned sibling lines too.
            const parentLine = this._getParentLine(this.selectedLine);
            if (parentLine) {
                lines = this.previousScannedLines.filter((line) =>
                    parentLine.virtual_ids.includes(line.virtual_id)
                );
            }
        } else if (configScanDest === "optional" && this.previousScannedLines?.length) {
            // If config is "After group of Products", get all previously scanned lines.
            for (const line of this.previousScannedLines) {
                if (!lines.find((l) => l.virtual_id === line.virtual_id)) {
                    lines.push(line);
                }
            }
        }
        if (this.previousScannedLinesByPackage?.length) {
            // In case some lines were added by scanning a package, get those lines.
            lines = this.previousScannedLinesByPackage;
        }

        return Array.from(new Set(lines));
    }

    _getLineMoveId(line) {
        return line.move_id;
    }

    _onExit() {
        if (["done", "cancel"].includes(this.record.state) || this.moveIds?.length === 0) {
            // No need to all post process if operation is closed or have no move.
            return;
        }
        const quantitiesByMove = this.initialState.lines.reduce((res, line) => {
            const moveId = this._getLineMoveId(line);
            if (res[moveId]) {
                res[moveId].quantity_done += line.qty_done;
                res[moveId].reserved_uom_qty += line.reserved_uom_qty;
            } else {
                res[moveId] = {
                    quantity_done: line.qty_done,
                    reserved_uom_qty: line.reserved_uom_qty,
                };
            }
            return res;
        }, {});
        return this.orm.call("stock.move", "post_barcode_process", [
            this.moveIds,
            quantitiesByMove,
        ]);
    }

    async _processLocationDestination(barcodeData) {
        const configScanDest = this.config.restrict_scan_dest_location;
        if (configScanDest == "no") {
            return;
        }
        // For planned transfers, check the scanned location is a part of transfer destination.
        if (
            this._useReservation &&
            !this._isSublocation(barcodeData.destLocation, this._defaultDestLocation())
        ) {
            barcodeData.stopped = true;
            const message = _t(
                "The scanned location doesn't belong to this operation's destination"
            );
            return this.notification(message, { type: "danger" });
        }

        // Change the destination of all concerned lines.
        const lines = this._getLinesToMove();
        for (const line of lines) {
            await this.changeDestinationLocation(barcodeData.destLocation.id, line);
        }
        barcodeData.stopped = true;
    }

    async _processPackage(barcodeData) {
        const { packageName } = barcodeData;
        const recPackage = barcodeData.package;
        if (barcodeData.packageType && !recPackage) {
            // Scanned a package type and no existing package: make a put in pack (forced package type).
            barcodeData.stopped = true;
            return await this._processPackageType(barcodeData);
        } else if (packageName && !recPackage) {
            // Scanned a non-existing package: make a put in pack.
            this.lastScanned.packageId = false;
            barcodeData.stopped = true;
            return await this._putInPack({ default_name: packageName });
        } else if (!recPackage) {
            return; // No package, package's type or package's name => Nothing to do.
        }
        const packLocation = recPackage.location_id
            ? this.cache.dbIdCache["stock.location"][recPackage.location_id]
            : false;
        if (recPackage.location_id && !packLocation) {
            // The package is in a location but the location was not found in the cache,
            // surely because this location is not related to this picking.
            return;
        }
        if (
            packLocation &&
            packLocation.id !== this._defaultDestLocation().id &&
            ((this.config.restrict_scan_source_location && packLocation.id !== this.location.id) ||
                (!this.config.restrict_scan_source_location &&
                    !this._isSublocation(packLocation, this.location)))
        ) {
            // Package is not located at the destination (result package) and is not located at the
            // scanned source location (or one of its sublocations) neither.
            return;
        }

        let alreadyDonePackId;
        let scannedPackages = false;
        for (const packageLine of this.packageLines) {
            if (!this._isPackageInPackage(packageLine.package_id, recPackage)) {
                continue;
            }
            // Scanned package is either a parent of a line package or the package itself,
            // thus need to validate all relevant lines.
            if (packageLine.qty_done) {
                alreadyDonePackId = recPackage.id;
                continue;
            }
            for (const line of packageLine.lines) {
                this.selectedLineVirtualId = line.virtual_id;
                await this._updateLineQty(line, { qty_done: line.reserved_uom_qty });
                this._markLineAsDirty(line);
                scannedPackages = true;
            }
        }
        if (alreadyDonePackId) {
            this.lastScanned.packageId = alreadyDonePackId;
            this.notification(_t("This package is already scanned."), { type: "danger" });
        }
        if (scannedPackages || alreadyDonePackId) {
            this.lastScanned.packageId = recPackage.id;
            barcodeData.stopped = true;
            return this.trigger("update");
        }

        // Scanned a package: fetches package's quant and creates a line for
        // each of them, except if the package is already scanned.
        // TODO: can check if quants already in cache to avoid to make a RPC if
        // there is all in it (or make the RPC only on missing quants).
        this.lastScanned.packageId = false;
        const res = await this.orm.call("stock.quant", "get_stock_barcode_data_records", [
            recPackage.contained_quant_ids,
        ]);
        this.cache.setCache(res.records);
        const quants = res.records["stock.quant"];
        // Do not allow extra products if they are not allowed
        if (!this.config.barcode_allow_extra_product) {
            const allowedProductIds = new Set(
                this.currentState.lines.map((line) => line.product_id.id)
            );
            if (quants.some((quant) => !allowedProductIds.has(quant.product_id))) {
                barcodeData.error = _t(
                    "This package contains extra products and extra products are not allowed on this operation."
                );
                return;
            }
        }
        // If the package is empty or is already at the destination location,
        // assign it to the last scanned line.
        const currentLine = this.selectedLine || this.lastScannedLine;
        if (
            currentLine &&
            (!quants.length || recPackage.location_id === currentLine.location_dest_id.id)
        ) {
            const linesToUpdate = [currentLine];
            if (this.config.restrict_put_in_pack === "optional") {
                // If the current line is not packed yet, we want to pack only unpacked lines,
                // but if the current line is packed, we want to pack only the lines who are
                // already packed but where the package isn't itself in another package.
                const filterFunction = !currentLine.result_package_id
                    ? (line) => !line.result_package_id
                    : (line) => line.result_package_id && !line.result_package_id.package_dest_id;
                linesToUpdate.push(
                    ...this.previousScannedLines.filter(
                        (line) =>
                            line.qty_done &&
                            line.virtual_id !== currentLine.virtual_id &&
                            filterFunction(line)
                    )
                );
            }
            if (!currentLine.result_package_id) {
                for (const line of linesToUpdate) {
                    await this._assignEmptyPackage(line, recPackage);
                }
            } else {
                const packageIds = linesToUpdate.map((l) => l.result_package_id?.id);
                await this._putPackInPack(packageIds, {
                    default_package_id: recPackage.id,
                });
            }
            barcodeData.stopped = true;
            this.lastScanned.packageId = recPackage.id;
            this.trigger("update");
            return;
        }

        if (this.location && (!packLocation || !this._isSublocation(packLocation, this.location))) {
            // Package not at the source location: can't add its content.
            return;
        }
        // Checks if the package is already scanned.
        let alreadyExisting = 0;
        for (const line of this.pageLines) {
            if (
                line.package_id &&
                line.package_id.id === recPackage.id &&
                this.getQtyDone(line) > 0
            ) {
                alreadyExisting++;
            }
        }
        if (alreadyExisting >= quants.length) {
            barcodeData.error = _t("This package is already scanned.");
            return;
        }

        if (alreadyExisting) {
            const userConfirmation = new Deferred();
            this.dialogService.add(ConfirmationDialog, {
                body: _t(
                    "You have already scanned %s items of this package. Do you want to scan the whole package?",
                    alreadyExisting
                ),
                title: _t("Scanning package"),
                cancel: () => userConfirmation.resolve(false),
                confirm: () => userConfirmation.resolve(true),
                close: () => userConfirmation.resolve(false),
            });
            if (!(await userConfirmation)) {
                barcodeData.stopped = true;
                return;
            }
        }

        // For each quants, creates or increments a barcode line.
        for (const quant of quants) {
            const quantUoM = this.cache.getRecord("uom.uom", quant.product_uom_id);
            const product = this.cache.getRecord("product.product", quant.product_id);
            const quantPackage = this.cache.getRecord("stock.package", quant.package_id);
            const searchLineParams = Object.assign({}, barcodeData, { product, quantPackage });
            let remaining_qty = quant.quantity;
            let qty_used = 0;
            while (remaining_qty > 0) {
                const currentLine = this._findLine(searchLineParams);
                if (currentLine) {
                    // Updates an existing line.
                    const uomFactor = quantUoM.factor / currentLine.product_uom_id.factor;
                    const lineQtyDiff = currentLine.reserved_uom_qty - currentLine.qty_done;
                    const qtyNeeded = Math.max(lineQtyDiff, 0) / uomFactor;
                    qty_used = qtyNeeded ? Math.min(qtyNeeded, remaining_qty) : remaining_qty;
                    const fieldsParams = this._convertDataToFieldsParams({
                        quantity: qty_used * uomFactor,
                        lotName: barcodeData.lotName,
                        lot: barcodeData.lot,
                        package: quant.package_id,
                        owner: barcodeData.owner,
                    });
                    await this.updateLine(currentLine, fieldsParams);
                } else {
                    // Creates a new line.
                    qty_used = remaining_qty;
                    const isEntirePack = qty_used === quant.quantity;
                    const fieldsParams = this._convertDataToFieldsParams({
                        product,
                        quantity: qty_used,
                        lot: quant.lot_id,
                        package: quant.package_id,
                        resultPackage: quant.package_id,
                        owner: quant.owner_id,
                        srcLocation: quant.location_id,
                        isEntirePack,
                    });
                    if (quant.package_id !== recPackage.id) {
                        fieldsParams.outermost_result_package_id = recPackage.id;
                    }
                    const newLine = await this._createNewLine({ fieldsParams });
                    if (isEntirePack) {
                        // Keep in memory what was the initial package line's quantity.
                        newLine.packedQuantity = qty_used;
                    }
                }
                remaining_qty -= qty_used;
            }
        }
        barcodeData.stopped = true;
        this.selectedLineVirtualId = false;
        this.lastScanned.packageId = recPackage.id;
        this.trigger("update");
    }

    async _processPackageType(barcodeData) {
        const { packageType } = barcodeData;
        if (!this.selectedLine && this.lastScannedPackages.length && packageType) {
            // One or multiple packages were previously scanned and a package
            // type is now scanned => Put the scanned package(s) in a new package.
            const packageIds = this.lastScannedPackages.map((pack) => pack.id);
            return await this._putPackInPack(packageIds, {
                default_package_type_id: packageType.id,
                default_name: barcodeData?.packageName,
            });
        }
        if (!this.selectedLine || !this.selectedLine.qty_done) {
            barcodeData.stopped = true;
            const message = _t(
                "You can't apply a package type. First, scan product or select a line"
            );
            return this.notification(message, { type: "warning" });
        }
        const resultPackage = this.selectedLine.result_package_id;
        if (!resultPackage) {
            // No package on the line => Do a put in pack.
            const additionalParams = { default_package_type_id: packageType.id };
            if (barcodeData.packageName) {
                additionalParams.default_name = barcodeData.packageName;
            }
            return await this._putInPack(additionalParams);
        } else if (!resultPackage.package_type_id) {
            // Changes the package type for the scanned one.
            await this.save();
            await this.orm.write("stock.package", [resultPackage.id], {
                package_type_id: packageType.id,
            });
            const message = _t("Package type %(type)s applied to the package %(package)s", {
                type: packageType.name,
                package: resultPackage.name,
            });
            this.notification(message, { type: "success" });
            return this.trigger("refresh");
        } else {
            // Put package(s) inside a new one of the scanned package type.
            const packageToPackIds = this.getPackageToPackIds();
            return this._putPackInPack(packageToPackIds, {
                default_package_type_id: packageType.id,
                default_name: barcodeData?.packageName,
            });
        }
    }

    async _putInPack(additionalParams = {}) {
        const context = { barcode_view: true };
        if (this.selectedLine?.result_package_id) {
            // If selected line is already packed, we do a "pack in pack" instead of a "put in pack"
            const packageToPackIds = this.getPackageToPackIds();
            return this._putPackInPack(packageToPackIds, context);
        }
        if (!this.groups.group_tracking_lot) {
            return this.notification(_t("To use packages, enable 'Packages' in the settings"), {
                type: "danger",
            });
        }
        // Before the put in pack, create a new empty move line with the remaining
        // quantity for each uncompleted move line who will be packaged.
        const lines = [...this.pageLines];
        for (const line of lines) {
            if (line.result_package_id || !this.shouldSplitLine(line)) {
                continue; // Line is already in a package or no quantity to process.
            }
            await this.splitLine(line);
        }
        await this.save();
        const result = await this.orm.call(this.resModel, "action_put_in_pack", [[this.resId]], {
            package_type_id: additionalParams.default_package_type_id,
            package_name: additionalParams.default_name,
            context,
        });
        if (typeof result === "object" && result.type) {
            return this.trigger("process-action", result);
        }
        this.trigger("refresh");
    }

    /**
     * Define which line must be packed, depending of the selected line.
     * If the selected line is already packed, pack other already packed lines.
     * If selected line is not packed, pack other no packed lines.
     * If selected line has some quantity, pack only lines with quantity.
     * @returns {Array<number>} list of packages' id
     */
    getPackageToPackIds() {
        const packageIds = [];
        // Define what level of packs need to be packed.
        const mustPackAlreadyPacked = Boolean(this.selectedLine.result_package_id.package_dest_id);
        const mustPackWithQuantity = Boolean(this.getQtyDone(this.selectedLine));
        for (const line of this.previousScannedLines) {
            if (mustPackAlreadyPacked && !line.result_package_id.package_dest_id) {
                continue;
            } else if (
                !mustPackAlreadyPacked &&
                (!line.result_package_id || line.result_package_id.package_dest_id)
            ) {
                continue;
            } else if (mustPackWithQuantity && !this.getQtyDone(line)) {
                continue;
            }
            packageIds.push(line.result_package_id.id);
        }
        return packageIds;
    }

    async _putPackInPack(packageIds, additionalParams = {}) {
        const context = { barcode_view: true };
        if (!this.groups.group_tracking_lot) {
            return this.notification(_t("To use packages, enable 'Packages' in the settings"), {
                type: "danger",
            });
        }
        if (!packageIds?.length) {
            // Nothing to do in this case
            return;
        }
        await this.save();
        const result = await this.orm.call("stock.package", "action_put_in_pack", [packageIds], {
            package_id: additionalParams.default_package_id,
            package_type_id: additionalParams.default_package_type_id,
            package_name: additionalParams.default_name,
            context,
        });
        if (typeof result === "object" && result.type) {
            this.trigger("process-action", result);
        } else {
            this.trigger("refresh");
        }
    }

    async unpack(linesToUnpack) {
        for (const line of linesToUnpack) {
            if (line.outermost_result_package_id) {
                await this.updateLine(line, { outermost_result_package_id: false });
            } else {
                await this.updateLine(line, { result_package_id: false });
            }
        }
        await this.save();
        this.trigger("update");
    }

    async _returnProducts() {
        const action = await this.orm.call(this.resModel, "action_create_return_picking", [
            [this.resId],
        ]);
        return this.action.doAction(action, { stackPosition: "replaceCurrentAction" });
    }

    async _scrap() {
        if (!this.canScrap) {
            const message = _t("You can't register scrap at this state of the operation");
            return this.notification(message, { type: "warning" });
        }
        await this.newScrapProduct();
    }

    /**
     * Set the pickings's responsible to the active user.
     */
    async _setUser() {
        if (this.record.id && this.record.user_id != user.userId) {
            this.record.user_id = user.userId;
            await this.orm.write(this.resModel, [this.record.id], { user_id: user.userId });
        }
    }

    _setLocationFromBarcode(result, location) {
        if (this.record.picking_type_code === "outgoing") {
            result.location = location;
        } else if (this.record.picking_type_code === "incoming") {
            result.destLocation = location;
        } else if (this.previousScannedLines.length || this.previousScannedLinesByPackage.length) {
            if (
                this.config.restrict_scan_source_location &&
                this.config.restrict_scan_dest_location === "no" &&
                this.barcodeInfo.class != "scan_dest"
            ) {
                result.location = location;
            } else {
                result.destLocation = location;
            }
        } else if (["scan_product_or_dest", "scan_dest"].includes(this.barcodeInfo.class)) {
            result.destLocation = location;
        } else {
            result.location = location;
        }
        return result;
    }

    _sortingMethod(l1, l2) {
        const l1IsCompleted = this._lineIsComplete(l1);
        const l2IsCompleted = this._lineIsComplete(l2);
        // Complete lines always on the bottom.
        if (!l1IsCompleted && l2IsCompleted) {
            return -1;
        } else if (l1IsCompleted && !l2IsCompleted) {
            return 1;
        }
        return super._sortingMethod(...arguments);
    }

    _updateLineQty(line, args) {
        if (args.qty_done) {
            if (line.product_id.tracking === "serial") {
                const nextQty = line.qty_done + args.qty_done;
                if (nextQty > 1 && (this.record.use_create_lots || this.record.use_existing_lots)) {
                    return; // Can't have more than 1 qty by serial number.
                }
            }
            line.qty_done += args.qty_done;
            this._setUser();
        }
    }

    _updateLotName(line, lotName) {
        line.lot_name = lotName;
    }

    _canOverrideTrackingNumber(line, newLotName) {
        return (
            super._canOverrideTrackingNumber(...arguments) ||
            (this.location.id === line.location_id.id &&
                !line.package_id &&
                !line.owner_id &&
                this.getQtyDone(line) === 0)
        );
    }

    async _processGs1Data(data) {
        const result = await super._processGs1Data(...arguments);
        const { rule } = data;
        if (
            result.location &&
            (rule.type === "location_dest" || this.barcodeInfo.class === "scan_product_or_dest")
        ) {
            result.destLocation = result.location;
            result.location = undefined;
        }
        return result;
    }

    _getCompanyId() {
        return this.record.company_id;
    }
}
