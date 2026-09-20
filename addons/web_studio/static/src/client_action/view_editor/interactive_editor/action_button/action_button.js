import { Component, useState } from "@odoo/owl";

export class AddButtonAction extends Component {
    static props = {};
    static template = `web_studio.AddButtonAction`;
    onClick(ev) {
        let nextButtonCount = 1;
        const findHeader =
            this.env.viewEditorModel.xmlDoc.firstChild.querySelector(":scope > header");
        if (!findHeader) {
            this.env.viewEditorModel.pushOperation({
                type: "statusbar",
                view_id: this.env.viewEditorModel.view.id,
            });
        } else {
            nextButtonCount = findHeader.querySelectorAll(":scope > button").length + 1
        }
        this.env.viewEditorModel.doOperation({
            type: "add_header_button",
        });
        this.env.setAutoClick({
            xpath: `/${this.env.viewEditorModel.viewType}[1]/header[1]/button[${nextButtonCount}]`,
        }, {});
    }
}

export class SelectionHeaderButtons extends Component {
    static props = {
        headerButtons: { type: Object },
    };
    static template = `web_studio.SelectionHeaderButtons`;
    static components = {
        AddButtonAction,
    };
    setup() {
        this.viewEditorModel = useState(this.env.viewEditorModel);
        this.buttons = this.getButtons();
    }
    makeTooltipButton(button) {
        return JSON.stringify({
            button: {
                string: button.string,
                type: button.clickParams?.type,
                name: button.clickParams?.name,
            },
            debug: true,
        });
    }
    getButtons() {
        if (this.viewEditorModel.showInvisible) {
            return this.props.headerButtons.map((btn) => {
                if (btn.invisible === "True" || btn.invisible === "1") {
                    btn.className += " o_web_studio_show_invisible";
                }
                return btn;
            });
        }
        return this.props.headerButtons.filter(
            (btn) => btn.invisible !== "True" && btn.invisible !== "1"
        );
    }
    getClassName(button) {
        return button.className.includes("btn-primary")
            ? button.className
            : `btn-secondary ${button.className}`;
    }
}
