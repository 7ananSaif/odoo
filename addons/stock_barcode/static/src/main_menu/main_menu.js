import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState, markup } from "@odoo/owl";
import { ManualBarcodeScanner } from "@barcodes/components/manual_barcode";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { url } from "@web/core/utils/urls";

export class MainMenu extends Component {
    static props = { ...standardActionServiceProps };
    static components = {};
    static template = "stock_barcode.MainMenu";

    setup() {
        const displayDemoMessage = this.props.action.params.message_demo_barcodes;
        this.actionService = useService("action");
        this.dialogService = useService("dialog");
        this.pwaService = useService("pwa");
        this.home = useService("home_menu");
        this.notificationService = useService("notification");
        this.state = useState({ displayDemoMessage });
        this.barcodeService = useService("barcode");
        useBus(this.barcodeService.bus, "barcode_scanned", (ev) =>
            this._onBarcodeScanned(ev.detail.barcode)
        );

        onWillStart(async () => {
            const data = await rpc("/stock_barcode/get_main_menu_data");
            this.locationsEnabled = data.groups.locations;
            this.packagesEnabled = data.groups.package;
            this.trackingEnabled = data.groups.tracking;
            this.quantCount = data.quant_count;
            this.soundEnable = data.play_sound;
            if (this.soundEnable) {
                const fileExtension = new Audio().canPlayType("audio/ogg; codecs=vorbis")
                    ? "ogg"
                    : "mp3";
                this.sounds = {
                    success: new Audio(
                        url(`/stock_barcode/static/src/audio/success.${fileExtension}`)
                    ),
                };
                this.sounds.success.load();
            }
        });
    }

    logout() {
        const path = `/web/session/logout${
            this.pwaService.isScopedApp ? "?redirect=scoped_app/barcode" : ""
        }`;
        window.open(path, "_self");
    }

    openManualBarcodeDialog() {
        let res;
        let rej;
        const promise = new Promise((resolve, reject) => {
            res = resolve;
            rej = reject;
        });
        this.dialogService.add(ManualBarcodeScanner, {
            facingMode: "environment",
            onResult: (barcode) => {
                this._onBarcodeScanned(barcode);
                res(barcode);
            },
            onError: (error) => rej(error),
        });
        promise.catch((error) => console.log(error));
        return promise;
    }

    removeDemoMessage() {
        const params = {
            title: _t("Don't show this message again"),
            body: _t(
                "Do you want to permanently remove this message ? " +
                    "It won't appear anymore, so make sure you don't need the barcodes sheet or you have a copy."
            ),
            confirm: () => {
                rpc("/stock_barcode/rid_of_message_demo_barcodes"); // Sets action message param false on server
                this.state.displayDemoMessage = false; // Remove message from current view
                this.props.action.params.message_demo_barcodes = false; // Remove message if using breadcrumbs
            },
            cancel: () => {},
            confirmLabel: _t("Remove it"),
            cancelLabel: _t("Leave it"),
        };
        this.dialogService.add(ConfirmationDialog, params);
    }

    playSound(soundName) {
        if (this.soundEnable) {
            this.sounds[soundName].currentTime = 0;
            this.sounds[soundName].play().catch((error) => {
                // `play` returns a promise. In case this promise is rejected (permission
                // issue for example), catch it to avoid Odoo's `UncaughtPromiseError`.
                this.soundEnable = false;
                console.warn(error);
            });
        }
    }

    async _onBarcodeScanned(barcode) {
        const res = await rpc("/stock_barcode/scan_from_main_menu", { barcode });
        if (res.action) {
            this.playSound("success");
            return this.actionService.doAction(res.action);
        }
        this.notificationService.add(res.warning, { type: "danger" });
    }

    /** Builds the barcode landing page bullet points, decribing features available depending on settings */
    get barcodeHomeHelper() {
        const tags = {
            bold_s: markup`<b>`,
            bold_e: markup`</b>`,
        };

        const bullets = [
            _t(
                "Scan a %(bold_s)sproduct%(bold_e)s or its %(bold_s)spackaging%(bold_e)s to locate it",
                tags
            ),
        ];
        // 2nd bullet point depends on which setting is activated
        if (this.packageEnabled && this.trackingEnabled) {
            bullets.push(
                _t(
                    "Scan a %(bold_s)stracking number%(bold_e)s or a %(bold_s)spackage%(bold_e)s to find a transfer",
                    tags
                )
            );
        } else if (this.packageEnabled) {
            bullets.push(_t("Scan a %(bold_s)spackage%(bold_e)s to find a transfer", tags));
        } else if (this.trackingEnabled) {
            bullets.push(_t("Scan a %(bold_s)stracking number%(bold_e)s to find a transfer", tags));
        }
        bullets.push(_t("Scan a %(bold_s)spicking%(bold_e)s to open it", tags));
        if (this.locationsEnabled) {
            bullets.push(_t("Scan a %(bold_s)slocation%(bold_e)s to initiate a transfer", tags));
        }
        bullets.push(_t("Scan an %(bold_s)soperation type%(bold_e)s to start it", tags));
        return bullets;
    }

    get demoMessage() {
        const demo_link = _t("Download demo data sheet");
        const barcode_link = _t("Download operation barcodes");

        const sheet_s = markup`<a href="/stock_barcode/static/img/barcodes_demo.pdf" target="_blank" aria-label="${demo_link}" title="${demo_link}">`;
        const ops_s = markup`<a href="/stock_barcode/print_inventory_commands?barcode_type=barcode_commands_and_operation_types" target="_blank" aria-label="${barcode_link}" title="${barcode_link}">`;
        const sheet_e = markup`</a>`;
        const ops_e = markup`</a>`;

        return _t(
            "Print the %(sheet_s)sdemo data sheet%(sheet_e)s to test, or %(ops_s)sbarcodes%(ops_e)s for operations.",
            { sheet_s, sheet_e, ops_s, ops_e }
        );
    }
}

registry.category("actions").add("stock_barcode_main_menu", MainMenu);
