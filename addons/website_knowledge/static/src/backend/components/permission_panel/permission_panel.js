import { patch } from "@web/core/utils/patch";

import { PermissionPanel } from "@knowledge/components/permission_panel/permission_panel";
import { CopyButton } from "@web/core/copy_button/copy_button";

patch(PermissionPanel.prototype, {
    onWebsitePublishedClick() {
        if (!this.userIsInternalEditor) {
            return;
        }
        this.toggleWebsitePublished();
    },
    async toggleWebsitePublished() {
        await this.record.update({'website_published': !this.record.data.website_published});
    },
});

PermissionPanel.components = {
    ...PermissionPanel.components,
    CopyButton,
};
