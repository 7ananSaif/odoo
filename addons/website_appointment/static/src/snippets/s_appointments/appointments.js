import { registry } from "@web/core/registry";
import { DynamicSnippet } from "@website/snippets/s_dynamic_snippet/dynamic_snippet";
import { Domain } from "@web/core/domain";


export class AppointmentsListSnippet extends DynamicSnippet {
    static selector = ".s_appointments";
    /**
     * @override
     */
    getSearchDomain() {
        let searchDomain = new Domain(super.getSearchDomain(...arguments));
        const snippetDataset = this.el.dataset;
        const filterType = snippetDataset.filterType;
        const appointmentNames = (snippetDataset.appointmentNames || '')
            .split(',')
            .map((name) => name.trim())
            .filter((name) => name.length > 0);

        if (filterType === 'users') {
            searchDomain = Domain.and([searchDomain, [['schedule_based_on', '=', 'users']]]);
            if (snippetDataset.filterUsers) {
                const filterUserIds = JSON.parse(snippetDataset.filterUsers).map(u => u.id);
                if (filterUserIds.length !== 0) {
                    searchDomain = Domain.and([searchDomain, [['staff_user_ids', 'in', filterUserIds]]]);
                }
            }
        } else if (filterType === 'resources') {
            searchDomain = Domain.and([searchDomain, [['schedule_based_on', '=', 'resources']]]);
            if (snippetDataset.filterResources) {
                const filterResourceIds = JSON.parse(snippetDataset.filterResources).map(r => r.id);
                if (filterResourceIds.length !== 0) {
                    searchDomain = Domain.and([searchDomain, [['resource_ids', 'in', filterResourceIds]]]);
                }
            }
        }
        if (appointmentNames.length > 0) {
            const nameDomains = appointmentNames.map((name) => [['name', 'ilike', name]]);
            searchDomain = Domain.and([searchDomain, Domain.or(nameDomains)]);
        }
        return searchDomain.toList();
    }
}

registry.category("public.interactions").add("website_appointment.appointments", AppointmentsListSnippet);

registry
    .category("public.interactions.edit")
    .add("website_appointment.appointments", {
        Interaction: AppointmentsListSnippet,
    });
