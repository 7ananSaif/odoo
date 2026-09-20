import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
import { HostManualSelection } from "@frontdesk/host_page/host_manual_selection";

export class HostPage extends Component {
    static template = "frontdesk.HostPage";
    static components = { HostManualSelection };
    static props = {
        setHostData: Function,
        showScreen: Function,
        stationId: Number,
        token: String,
        theme: String,
    };

    setup() {
        this.state = useState({
            showManualSelection: false,
            hostName: "",
        });
    }

    /**
     * This method is triggered when the confirm button is clicked.
     * It sets the host data and displays the RegisterPage component.
     *
     * @private
     */
    _onConfirm() {
        this.props.setHostData(this.host);
        this.props.showScreen("RegisterPage");
    }

    /**
     * @param {object | null} host
     */
    selectedHost(host) {
        this.host = host;
        this.state.hostName = host?.display_name ?? "";
        this.state.showManualSelection = false;
    }

    showManualSelection() {
        this.state.showManualSelection = true;
    }

    goBackFromManualSelection() {
        this.state.showManualSelection = false;
    }
}

registry.category("frontdesk_screens").add("HostPage", HostPage);
