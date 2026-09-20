declare module "models" {
    import { WhatsAppAccount as WhatsAppAccount2 } from "@whatsapp/core/common/whatsapp_account_model";

    export interface WhatsAppAccount extends WhatsAppAccount2 { }
    export interface Message {
        whatsappStatus: string,
    }

    export interface Models {
        "whatsapp.account": WhatsAppAccount,
    }
}
