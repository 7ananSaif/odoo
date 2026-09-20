import { Component, useState, onWillUpdateProps } from "@odoo/owl";

export class SignSaveTemplateDialog extends Component {
    static template = "sign.SignSaveTemplateDialog";
    static components = {};
    static props = {
        isShown: { type: Boolean },
        documentUsedTimesCounter: { type: Number },
        onTemplateSaveClick: { type: Function },
    };

    setup() {
        this.state = useState({
            isShown: this.props.isShown,
        })

        onWillUpdateProps((nextProps) => {
            this.props = nextProps;
            this.state.isShown = this.props.documentUsedTimesCounter > 2;
        });
    }
}
