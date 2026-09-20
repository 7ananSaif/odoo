import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { Notebook } from "@web/core/notebook/notebook";
import { FormRenderer } from "@web/views/form/form_renderer";
import { FormCompiler } from "@web/views/form/form_compiler";
import { onMounted, onPatched } from "@odoo/owl";

export class RuleFormNotebook extends Notebook {
    static props = {
        ...Notebook.props,
        onValueCheck: { type: Function, optional: true },
    };

    setup() {
        super.setup();
        const applyStyles = () => this.props.onValueCheck && this.props.onValueCheck();
        onMounted(applyStyles);
        onPatched(applyStyles);
    }
}

export class RuleFormRenderer extends FormRenderer {
    static components = {
        ...FormRenderer.components,
        Notebook: RuleFormNotebook,
    };

    _toggleClass(contentEl, condition, className) {
        contentEl.classList.toggle(className, condition);
    }

    async _applyStylesToElements(contentElements) {
        const { record: { data } } = this.props;
        if (!contentElements.length) return;

        contentElements.forEach((contentEl) => {
            this._toggleClass(contentEl, data.bold, 'fw-bold');
            this._toggleClass(contentEl, data.italic, 'fst-italic');
            this._toggleClass(contentEl, data.underline, 'text-decoration-underline');
            this._toggleClass(contentEl, data.space_above, 'pt-4');
            this._toggleClass(contentEl, data.indented, 'ps-4');
            this._toggleClass(contentEl, data.title && contentEl.classList.contains('o_field_monetary'), 'd-none');
            contentEl.style.color = data.color || '';
        });
    }

    async saveChanges() {
        const contentElements = document.querySelectorAll('.o_preview');
        await this._applyStylesToElements(contentElements);
    }
}

export class RuleFormCompiler extends FormCompiler {
    compileNotebook(el, params) {
        const notebook = super.compileNotebook(...arguments);
        notebook.setAttribute('onValueCheck', '() => __comp__.saveChanges()');
        return notebook;
    }
}

export const ruleFormView = {
    ...formView,
    ...FormCompiler,
    Renderer: RuleFormRenderer,
    Compiler: RuleFormCompiler,
};

registry.category("views").add("hr_salary_rule_preview", formView);
