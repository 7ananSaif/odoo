import { Chatter } from "@mail/chatter/web_portal/chatter";

export class BankRecChatter extends Chatter {
    static props = [...Chatter.props, "statementLine?"];

    async reloadParentView() {
        await this.props.statementLine?.load();
    }
}
