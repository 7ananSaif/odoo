import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { patch } from "@web/core/utils/patch";

patch(PosOrderline.prototype, {
    canBeMergedWith(orderline) {
        // The Blackbox doesn't allow lines with a quantity of 5 numbers.
        if (
            !this.order_id.useBlackBoxBe() ||
            (this.order_id.useBlackBoxBe() && this.getQuantity() < 9999)
        ) {
            return super.canBeMergedWith(orderline);
        }
        return false;
    },
    _generateTranslationTable() {
        const replacements = [
            ["ÄÅÂÁÀâäáàã", "A"],
            ["Ææ", "AE"],
            ["ß", "SS"],
            ["çÇ", "C"],
            ["ÎÏÍÌïîìí", "I"],
            ["€", "E"],
            ["ÊËÉÈêëéè", "E"],
            ["ÛÜÚÙüûúù", "U"],
            ["ÔÖÓÒöôóò", "O"],
            ["Œœ", "OE"],
            ["ñÑ", "N"],
            ["ýÝÿ", "Y"],
        ];

        const lowercaseAsciiStart = "a".charCodeAt(0);
        const lowercaseAsciiEnd = "z".charCodeAt(0);

        for (
            let lowercaseAsciiCode = lowercaseAsciiStart;
            lowercaseAsciiCode <= lowercaseAsciiEnd;
            lowercaseAsciiCode++
        ) {
            const lowercaseChar = String.fromCharCode(lowercaseAsciiCode);
            const uppercaseChar = lowercaseChar.toUpperCase();
            replacements.push([lowercaseChar, uppercaseChar]);
        }

        const lookupTable = {};
        for (let i = 0; i < replacements.length; i++) {
            const letterGroup = replacements[i];
            const specialChars = letterGroup[0];
            const uppercaseReplacement = letterGroup[1];

            for (let j = 0; j < specialChars.length; j++) {
                const specialChar = specialChars[j];
                lookupTable[specialChar] = uppercaseReplacement;
            }
        }

        return lookupTable;
    },
    generatePluLine() {
        // |--------+-------------+-------+-----|
        // | AMOUNT | DESCRIPTION | PRICE | VAT |
        // |      4 |          20 |     8 |   1 |
        // |--------+-------------+-------+-----|

        // steps:
        // 1. replace all chars
        // 2. filter out forbidden chars
        // 3. build PLU line

        let amount = this._getAmountForPlu();
        let description = this.getProduct().display_name;
        let price_in_eurocent = this.prices.total_included * 100;
        const tax_labels = this.getLineTaxLabels();

        amount = this._prepareNumberForPlu(amount, 4);
        description = this._prepareDescriptionForPlu(description);
        price_in_eurocent = this._prepareNumberForPlu(price_in_eurocent, 8);

        return amount + description + price_in_eurocent + tax_labels;
    },
    _prepareNumberForPlu(number, field_length) {
        number = Math.abs(number);
        number = Math.round(number);

        let number_string = number.toFixed(0);

        number_string = this._replaceHashAndSignChars(number_string);
        number_string = this._filterAllowedHashAndSignChars(number_string);

        // get the required amount of least significant characters
        number_string = number_string.substr(-field_length);

        // pad left with 0 to required size
        while (number_string.length < field_length) {
            number_string = "0" + number_string;
        }

        return number_string;
    },
    _prepareDescriptionForPlu(description) {
        description = this._replaceHashAndSignChars(description);
        description = this._filterAllowedHashAndSignChars(description);

        // get the 20 most significant characters
        description = description.substr(0, 20);

        // pad right with SPACE to required size of 20
        while (description.length < 20) {
            description = description + " ";
        }

        return description;
    },
    _getAmountForPlu() {
        let amount = this.getQuantity();
        const uom = this.getUnit();

        if (uom.is_unit) {
            return amount;
        } else {
            const gramUom = this.models["uom.uom"].find((uom) => uom.name === "g");
            const litreUom = this.models["uom.uom"].find((uom) => uom.name === "L");

            const hasCommonReference = (uom1, uom2) => {
                const uom1Path = uom1.parent_path.split("/");
                const uom2Path = uom2.parent_path.split("/");
                const commonPath = [];
                for (let i = 0; i < Math.min(uom1Path.length, uom2Path.length); i++) {
                    if (uom1Path[i] === uom2Path[i]) {
                        commonPath.push(uom1Path[i]);
                    } else {
                        break;
                    }
                }
                return commonPath.length > 0;
            };

            if (gramUom && hasCommonReference(uom, gramUom)) {
                amount = (amount * uom.factor) / gramUom.factor;
            } else if (litreUom && hasCommonReference(uom, litreUom)) {
                amount = (amount * uom.factor) / litreUom.factor / 1000;
            }

            return amount;
        }
    },
    _replaceHashAndSignChars(str) {
        if (typeof str !== "string") {
            throw "Can only handle strings";
        }

        const translationTable = this._generateTranslationTable();

        const replaced_char_array = str.split("").map((char) => {
            const translation = translationTable[char];
            return translation !== undefined ? translation : char;
        });

        return replaced_char_array.join("");
    },
    // for hash and sign the allowed range for DATA is:
    //   - A-Z
    //   - 0-9
    // and SPACE as well. We filter SPACE out here though, because
    // SPACE will only be used in DATA of hash and sign as description
    // padding
    _filterAllowedHashAndSignChars(str) {
        if (typeof str !== "string") {
            throw "Can only handle strings";
        }

        const filtered_char_array = str.split("").filter((char) => {
            const ascii_code = char.charCodeAt(0);

            if (
                (ascii_code >= "A".charCodeAt(0) && ascii_code <= "Z".charCodeAt(0)) ||
                (ascii_code >= "0".charCodeAt(0) && ascii_code <= "9".charCodeAt(0))
            ) {
                return true;
            } else {
                return false;
            }
        });

        return filtered_char_array.join("");
    },
    getLineTaxLabels() {
        return this.product_id.taxes_id?.map((tax) => tax.tax_group_id.pos_receipt_label).join(" ");
    },
});
