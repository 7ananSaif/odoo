import { browser } from "@web/core/browser/browser";
import { ListRenderer } from "@web/views/list/list_renderer";
import { PayslipActionHelper } from "../../components/payslip_action_helper/payslip_action_helper";

export class PayslipListRenderer extends ListRenderer {
    static template = "hr_payroll.PayslipListRenderer";
    static components = {
        ...ListRenderer.components,
        PayslipActionHelper,
    };
    static props = [
        ...ListRenderer.props,
        "onGenerate",
        "payRunInfo",
    ];

    setup() {
        super.setup();
        this.keyPayrunOptionalFields = `payrun_${this.keyOptionalFields}`;
    }

    get payslipActionHelperProps() {
        const helperProps = {
            onClickCreate: this.props.onAdd.bind(this.onClickCreate),
            onClickGenerate: this.props.onGenerate.bind(this.onGenerate),
        };
        if (this.props.payRunInfo.id) {
            helperProps.payrunId = this.props.payRunInfo.id;
        }
        return helperProps;
    }

    /** utils **/
    get inPayrun() {
        return this.props?.payRunInfo?.id;
    }

    /** overrides **/
    /**
     * @override
     */
    getActiveColumns(list) {
        if (this.inPayrun) {
            this.allColumns = this.allColumns.map((col) => (
                col.options && 'payrun_optional' in col.options
                    ? {...col, optional: col.options.payrun_optional}
                    : col
            ));
        }
        return super.getActiveColumns(list);
    }

    saveOptionalActiveFields() {
        const storageKey = this.inPayrun ? this.keyPayrunOptionalFields : this.keyOptionalFields;
        browser.localStorage.setItem(
            storageKey,
            Object.keys(this.optionalActiveFields).filter(
                (fieldName) => this.optionalActiveFields[fieldName]
            )
        );
    }

    computeOptionalActiveFields() {
        const storageKey = this.inPayrun ? this.keyPayrunOptionalFields : this.keyOptionalFields;
        const localStorageValue = browser.localStorage.getItem(storageKey);
        const optionalColumn = this.allColumns.filter(
            (col) => col.type === "field" && (col.optional || this.inPayrun && col.options?.payrun_optional)
        );
        const optionalActiveFields = {};
        if (localStorageValue !== null) {
            const localStorageOptionalActiveFields = localStorageValue.split(",");
            for (const col of optionalColumn) {
                optionalActiveFields[col.name] = localStorageOptionalActiveFields.includes(
                    col.name
                );
            }
        } else {
            for (const col of optionalColumn) {
                if (this.inPayrun && col.options?.payrun_optional) {
                    optionalActiveFields[col.name] = col.options?.payrun_optional === "show";
                }
                else {
                    optionalActiveFields[col.name] = col.optional === "show";
                }
            }
        }
        return optionalActiveFields;
    }
}
