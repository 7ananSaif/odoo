import { registry } from "@web/core/registry";

// See `HtmlUpgradeManager` docstring for usage details.
const html_upgrade = registry.category("html_editor_upgrade");

// Handle the conversion of `o_knowledge_behavior_anchor` elements to their
// `data-embedded` counterpart, when loading the value of a html_field.
html_upgrade.category("1.0").add("knowledge", "@knowledge/editor/html_migrations/migration-1.0");

// embeddedViews favorite irFilters should have a `user_ids` property
html_upgrade.category("2.0").add("knowledge", "@knowledge/editor/html_migrations/migration-2.0");
