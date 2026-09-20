import { BaseOptionComponent } from "@html_builder/core/utils";
import { Plugin } from "@html_editor/plugin";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

export class WebsiteAppointmentPageOption extends BaseOptionComponent {
  static template = "website_appointment.WebsiteAppointmentPageOption";
  static selector = "main:has(.o_appointment_index)";
  static title = _t("Appointments Page");
  static groups = ["website.group_website_designer"];
  static editableOnly = false;
}

export class WebsiteAppointmentPageOptionPlugin extends Plugin {
  static id = "websiteAppointmentPageOption";
  resources = {
    builder_options: [WebsiteAppointmentPageOption],
  };
}

registry
  .category("website-plugins")
  .add(WebsiteAppointmentPageOptionPlugin.id, WebsiteAppointmentPageOptionPlugin);
