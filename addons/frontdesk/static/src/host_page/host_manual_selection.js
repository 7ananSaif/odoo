import { Component, useState, onWillStart } from "@odoo/owl";
import { Domain } from "@web/core/domain";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { Pager } from "@web/core/pager/pager";
import { MEDIAS_BREAKPOINTS, SIZES } from "@web/core/ui/ui_service";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";

export class HostManualSelection extends Component {
    static template = "frontdesk.HostManualSelection";
    static components = {
        Dropdown,
        DropdownItem,
        Pager,
    };
    static props = {
        stationId: Number,
        token: String,
        theme: String,
        onSelectHost: Function,
        onClickBack: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            hostsData: {
                count: 0,
                records: [],
            },
            departments: [],
            offset: 0,
            limit: this.calculateLimit(),
            searchInput: "",
            searchDomain: [],
            departmentDomain: [],
        });
        this.departmentName = _t("All departments");
        this.debouncedSearch = useDebounced(this._performSearch, 250);
        onWillStart(async () => {
            await this._fetchDepartments();
            await this._fetchHostData();
        });
    }

    calculateLimit() {
        // This function calculates the maximum number of host cards that can fit on the screen based on its size,
        // font size, and the number of cards per row.
        let hostCardPerLine = 1;
        let fontSizeMultiplication = 1;
        let searchBarHeight = 0;
        if (screen.width <= MEDIAS_BREAKPOINTS[SIZES.SM].maxWidth) {
            searchBarHeight += 38;
        } else if (screen.width <= MEDIAS_BREAKPOINTS[SIZES.MD].maxWidth) {
            hostCardPerLine = 2;
        } else if (screen.width <= MEDIAS_BREAKPOINTS[SIZES.LG].maxWidth) {
            fontSizeMultiplication *= 1.25;
            hostCardPerLine = 2;
        } else if (screen.width <= MEDIAS_BREAKPOINTS[SIZES.XL].maxWidth) {
            fontSizeMultiplication *= 1.25;
            if (screen.width < 1400) {
                hostCardPerLine = 3;
            } else {
                hostCardPerLine = 4;
            }
        } else {
            hostCardPerLine = 4;
            if (screen.width <= 2560) {
                fontSizeMultiplication *= 1.35;
            } else {
                fontSizeMultiplication *= 2;
            }
        }
        const hostCardHeight = 150 * fontSizeMultiplication;
        searchBarHeight += 62 * fontSizeMultiplication;
        const availableScreen = screen.height - searchBarHeight;
        return Math.trunc(availableScreen / hostCardHeight) * hostCardPerLine;
    }

    async _onPagerChanged({ offset, limit }) {
        this.state.offset = offset;
        this.state.limit = limit;
        await this._fetchHostData();
    }

    async _fetchDepartments() {
        const departments = await rpc(`/frontdesk/${this.props.stationId}/${this.props.token}/get_departments`);
        this.state.departments = departments;
    }

    async _fetchHostData() {
        const domain = Domain.and([this.state.departmentDomain, this.state.searchDomain]).toList();
        const results = await rpc(`/frontdesk/${this.props.stationId}/${this.props.token}/hosts_infos`, {
            limit: this.state.limit,
            offset: this.state.offset,
            domain: domain,
        });
        this.state.hostsData.records = results.records;
        this.state.hostsData.count = results.length;
    }

    async onDepartmentClick(departmentId = false) {
        if (this.env.isSmall) {
            if (departmentId) {
                const selectedDepartment = this.state.departments.find((department) => department.id === departmentId);
                this.departmentName = selectedDepartment.name;
            } else {
                this.departmentName = _t("All departments");
            }
        }
        this.state.departmentDomain = departmentId ? [["department_id", "=", departmentId]] : [];
        this.state.offset = 0;
        await this._fetchHostData();
    }

    async _performSearch(searchInput) {
        this.state.searchDomain = searchInput.length ? [["display_name", "ilike", searchInput]] : [];
        this.state.offset = 0;
        await this._fetchHostData();
    }

    onSearchInput(ev) {
        const searchInput = ev.target.value.trim();
        this.debouncedSearch(searchInput);
    }

    onSelectHost(hostId) {
        const host = this.state.hostsData.records.find(h => h.id === hostId);
        if (host) {
            this.props.onSelectHost({
                id: host.id,
                display_name: host.display_name,
            });
        }
    }
}
