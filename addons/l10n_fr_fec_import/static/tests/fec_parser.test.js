import { expect, globals, test } from "@odoo/hoot";
import { deepEqual } from "@web/core/utils/objects";
import { useFECParser } from "@l10n_fr_fec_import/hooks/fec_parser_hook";
import { patchTranslations } from "@web/../tests/web_test_helpers";

async function readFecTestFile(fileName, format) {
    const filePath = `/l10n_fr_fec_import/static/tests/fec_test_files/${fileName}`;
    const response = await globals.fetch.call(window, filePath);
    const fileUnit8Array = new Uint8Array(await response.arrayBuffer());

    if (format === "base64") {
        return btoa(String.fromCharCode(...fileUnit8Array));
    }

    return new TextDecoder().decode(fileUnit8Array);
}

test("Test parsing of FEC files", async () => {
    patchTranslations();
    const fecParser = useFECParser();
    const fecFiles = [
        "fec_lf_tab_utf8.txt",
        "fec_lf_pipe_iso.txt",
        "fec_crlf_tab_utf8bom_large.csv",
        "fec_cr_tab_utf8_imbalanced_day.txt",
        "fec_lf_tab_utf8_imbalanced_month.txt",
        "fec_lf_tab_utf8_imbalanced.txt",
    ];
    for (const fecFile of fecFiles) {
        const data = await readFecTestFile(fecFile, "base64");
        // size is set to truthy value to avoid throwing an error in FECParser constructor
        const file = { size: true, data };
        const actualChunks = fecParser.parse(file);
        const expectedChunks = JSON.parse(await readFecTestFile(fecFile.split(".")[0] + ".json"));
        expect(deepEqual(expectedChunks, actualChunks)).toBe(true);
    }
});
