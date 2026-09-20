import { CallInvitation } from "@voip/softphone/call_invitation";

import { SmsButton } from "@voip_sms/sms_button";

CallInvitation.components = { ...CallInvitation.components, SmsButton };
