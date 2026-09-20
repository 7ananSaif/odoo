import { FormController } from "@web/views/form/form_controller";

export class SalaryCalculatorFormController extends FormController {
    get modelParams(){
        let params = super.modelParams;
        params.hooks.onRecordChanged = (record) => {
            record.save();
        }
        return params;
    }
}
