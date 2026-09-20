import { Asserts } from "./asserts";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("account_reports_annotations", {
    url: "/odoo/action-account_reports.action_account_report_bs",
    steps: () => [
        //--------------------------------------------------------------------------------------------------------------
        // Annotations
        //--------------------------------------------------------------------------------------------------------------
        // Test the initial status of annotations - There are 2 annotations to display
        {
            content: "Initial annotations",
            trigger: ".o_content",
            run: () => {
                Asserts.DOMContainsNone(".annotations");
            },
        },
        {
            content: "Unfold first line",
            trigger: "tr:nth-child(4) td:first()",
            run: "click",
        },
        {
            content: "Unfold second line",
            trigger: "tr:nth-child(7) td:first()",
            run: "click",
        },
        {
            content: "Unfold third line",
            trigger: "tr:nth-child(10) td:first()",
            run: "click",
        },
        {
            content: "Extra Trigger step",
            trigger: "tr:nth-child(5) .o_account_report_chatter_annoted",
        },
        {
            content: "Extra Trigger step",
            trigger: "tr:nth-child(12) .o_account_report_chatter_annoted",
        },
        {
            content: "Check there are two lines annotated initially",
            trigger: ".o_content",
            run: () => {
                const annotations = document.querySelectorAll(
                    ".btn_annotation.o_account_report_chatter_annoted"
                );

                // Check the number of annotated lines
                Asserts.isEqual(annotations.length, 2);
            },
        },
        // Test that we can add a new annotation
        {
            content: "Click to show caret option",
            trigger: "tr:nth-child(8) .btn_annotation:not(:visible)",
            run: "click",
        },
        {
            content: "Add a log note",
            trigger: ".o-mail-Chatter-logNote",
            run: "click",
        },
        {
            content: "Add text to annotate",
            trigger: ".o-mail-Composer-inputContainer textarea",
            run: "edit Annotation 121000",
        },
        {
            content: "Submit by logging the note",
            trigger: ".o-mail-Composer-send",
            run: "click",
        },
        {
            content: "Close Chatter",
            trigger: ".o_control_panel .btn-secondary[data-tooltip='Chatter']",
            run: "click",
        },
        {
            content: "Wait for annotation created",
            trigger: "tr:nth-child(8) .o_account_report_chatter_annoted",
        },
        {
            content: "Check there are now three lines annotated",
            trigger: ".o_content",
            run: () => {
                const annotations = document.querySelectorAll(
                    ".btn_annotation.o_account_report_chatter_annoted"
                );

                // Check the number of annotated lines
                Asserts.isEqual(annotations.length, 3);
            },
        },
        // Test that we can edit an annotation
        {
            content: "Open second annotated line annotation popover",
            trigger: "tr:nth-child(8) .btn_annotation",
            run: "click",
        },
        {
            content: "Select the edit button",
            trigger: ".o-mail-Message:last-child .btn[name='edit']:not(:visible)",
            run: "click",
        },
        {
            content: "Annotate contains previous text value",
            trigger: ".o-mail-Message:last-child .o-mail-Composer-inputContainer textarea",
            run: () => {
                Asserts.isEqual(document.querySelector("textarea").value, "Annotation 121000");
            },
        },
        {
            content: "Add text to annotate",
            trigger: ".o-mail-Message:last-child .o-mail-Composer-inputContainer textarea",
            run: "edit Annotation 121000 edited",
        },
        {
            content: "Annotation is edited",
            trigger: ".o-mail-Message:last-child .o-mail-Composer-inputContainer textarea",
            run: () => {
                Asserts.isEqual(
                    document.querySelector(
                        ".o-mail-Message:last-child .o-mail-Composer-inputContainer textarea"
                    ).value,
                    "Annotation 121000 edited"
                );
            },
        },
        {
            content: "Save the annotation",
            trigger: ".o-mail-Message:last-child .btn[data-type='save']",
            run: "click",
        },
        {
            content: "Close Chatter",
            trigger: ".o_control_panel .btn-secondary[data-tooltip='Chatter']",
            run: "click",
        },
        // Test that we dont show there is an annotation if we delete the only annotation of a line
        {
            content: "Open Third annotated line annotation popover",
            trigger: "tr:nth-child(12) .btn_annotation",
            run: "click",
        },
        {
            content: "Wait for the messages to load",
            trigger: ".o-mail-Message",
        },
        {
            content: "Expand the options of the message",
            trigger: ".o-mail-Message:last-child button:has(i.oi-ellipsis-v):not(:visible)",
            run: "click",
        },
        {
            content: "Click on trash can",
            trigger: ".o_popover .o-dropdown-item:has(i.fa-trash)",
            run: "click",
        },
        {
            content: "Wait for the modal to appear",
            trigger: ".modal",
        },
        {
            content: "Confirm deletion of the annotation",
            trigger: ".modal-footer .btn-primary",
            run: "click",
        },
        {
            content: "Close Chatter",
            trigger: ".o_control_panel .btn-secondary[data-tooltip='Chatter']",
            run: "click",
        },
        {
            content: "Check there are now only two lines annotated",
            trigger: "tr:nth-child(12):not(:has(.fa-commenting))",
            run: () => {
                const annotations = document.querySelectorAll(
                    ".btn_annotation.o_account_report_chatter_annoted"
                );

                // Check the number of annotated lines
                Asserts.isEqual(annotations.length, 2);
            },
        },
    ],
});
