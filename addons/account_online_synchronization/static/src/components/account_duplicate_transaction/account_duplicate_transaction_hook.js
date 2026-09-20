import { useService } from "@web/core/utils/hooks";

export function useCheckDuplicateService() {
    return useService("account_online_synchronization.duplicate_check_service");
}
