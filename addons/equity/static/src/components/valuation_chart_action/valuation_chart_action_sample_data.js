import { user } from "@web/core/user";

export function useValuationChartActionSampleData() {
    function getSampleData() {
        const company = user.activeCompany;
        return {
            "labels": [company.name],
            "data": {
                "Nov 2024": [0],
                "Dec 2024": [0],
                "Jan 2025": [0],
                "Feb 2025": [0],
                "Mar 2025": [100],
                "Apr 2025": [200],
                "May 2025": [200],
                "Jun 2025": [400],
                "Jul 2025": [400],
                "Aug 2025": [900],
                "Sep 2025": [700],
                "Oct 2025": [800]
            },
        };
    };
    return {
        getSampleData,
    };
}
