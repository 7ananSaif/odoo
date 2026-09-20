import { user } from "@web/core/user";

export function useCapTableSampleData() {
    function getSampleData() {
        const company = user.activeCompany;

        const partnerHolderData = {};
        partnerHolderData[company.id] = {
            "2": {
                "classes": {
                    "1": 5,
                    "2": 8
                },
                "ownership": 0.13,
                "voting_rights": 0.19,
                "dividend_payout": 0.13,
                "dilution": 0.02,
                "valuation": 20
            },
            "3": {
                "classes": {
                    "1": 5,
                    "2": 2,
                    "3": 80,
                    "4": 420
                },
                "ownership": 0.87,
                "voting_rights": 0.81,
                "dividend_payout": 0.87,
                "dilution": 0.69,
                "valuation": 690
            },
            "4": {
                "classes": {
                    "4": 100
                },
                "ownership": 0,
                "voting_rights": 0,
                "dividend_payout": 0,
                "dilution": 0.14,
                "valuation": 140
            },
            "false": {
                "classes": {
                    "5": 120
                },
                "ownership": 0,
                "voting_rights": 0,
                "dividend_payout": 0,
                "dilution": 0.15,
                "valuation": 150
            }
        };
        const partnerClassesIds = {};
        partnerClassesIds[company.id] = [1, 2, 3, 4, 5];
        return {
            "partner_holder_data": partnerHolderData,
            "partner_classes_ids": partnerClassesIds,
            "partner_data": {
                "1": {
                    "display_name": company.name,
                    "equity_currency_id": 1,
                },
                "2": {
                    "display_name": "Marc Demo",
                    "equity_currency_id": 1,
                },
                "3": {
                    "display_name": "Joel Willis",
                    "equity_currency_id": 1,
                },
                "4": {
                    "display_name": "Julie Richards",
                    "equity_currency_id": 1,
                }
            },
            "class_data": {
                "1": {
                    "display_name": "ORD"
                },
                "2": {
                    "display_name": "Class A"
                },
                "3": {
                    "display_name": "Class B"
                },
                "4": {
                    "display_name": "Option Pool 1"
                },
                "5": {
                    "display_name": "Option pool 2"
                }
            }
        };
    }
    return {
        getSampleData,
    };
}
