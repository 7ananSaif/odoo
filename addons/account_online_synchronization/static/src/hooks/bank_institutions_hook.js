import { useService } from "@web/core/utils/hooks";

export function useBankInstitutions() {
    const orm = useService("orm");
    function fetch(journalId) {
        return new Promise((resolve, reject) => {
            orm.silent
                .call("account.journal", "fetch_online_sync_favorite_institutions", [journalId])
                .then((response) => {
                    resolve(response);
                })
                .catch((error) => {
                    reject(error);
                });
        });
    }
    return {
        fetch,
    };
}
