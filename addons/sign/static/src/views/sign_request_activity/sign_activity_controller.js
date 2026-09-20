import { ActivityController } from "@mail/views/web/activity/activity_controller";

export class SignActivityController extends ActivityController {
    get getSelectCreateDialogProps() {
        let dialogProps = super.getSelectCreateDialogProps;
        dialogProps = {
            ...dialogProps,
            noCreate: true,
            context: {
                ...dialogProps.context,
                show_upload_button: !this.props.context.show_upload_button,
            },
        };
        return dialogProps
    }
}
