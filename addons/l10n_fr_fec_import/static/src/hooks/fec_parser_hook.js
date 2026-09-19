import { _t } from "@web/core/l10n/translation";
import { floatIsZero } from "@web/core/utils/numbers";

export function useFECParser() {
    const maxLines = 1e3; // maximum size of each chunk (1,000 lines)
    const possibleDelimiters = /[\t|]/; // Matches any of the characters \t (tab) or |

    let header, fieldRegex;

    function parse(fecFile) {
        if (!fecFile.size) {
            throw new Error(_t("The FEC file has invalid size"));
        }

        const csvText = decodeAttachment(fecFile.data);
        const lines = csvText.split(/\r?\n|\r/);
        if (lines.length && !lines.at(-1).trim()) {
            // remove last line if empty
            lines.pop();
        }
        if (!lines.length) {
            throw new Error(_t("The FEC file cannot be empty"));
        }

        const headerText = lines[0];
        lines.shift(); // to remove the header
        const delimiter = headerText.match(possibleDelimiters)?.[0];
        if (delimiter) {
            // Fields are either surrounded by double quotes or separated by the delimiter
            const regexPattern = `(?<=^|[${delimiter}])(?:"[^"]*"|[^"${delimiter}]*)(?=[${delimiter}]|$)`;
            fieldRegex = new RegExp(regexPattern, "g");
        } else {
            throw new Error(_t("The zones should be separated by tab or the character '|'"));
        }
        header = splitLine(headerText);

        const incompleteLines = [];
        const processedLines = lines.map((line) => splitLine(line));
        processedLines.forEach((line, lineIndex) => {
            const lineNumber = lineIndex + 2; // 1 for the 0-based indexing, and 1 to compensate removed header
            if (!getMoveName(line)) {
                throw new Error(_t("Line %s does not have a valid move name", lineNumber));
            }
            if (line.length < header.length) {
                incompleteLines.push(lineNumber);
            }
        });
        if (incompleteLines.length) {
            throw new Error(
                _t(
                    `Some lines do not have the same number of fields as the header.
                    Please check the following line numbers:
                    %s`,
                    incompleteLines
                )
            );
        }

        const moves = processedLines.reduce((group, line) => {
            // group lines by move name
            const key = getMoveName(line);
            if (!group[key]) {
                group[key] = [];
            }
            group[key].push(line);
            return group;
        }, {});

        const chunks = [];
        const unbalancedChunks = Array.from({ length: 12 }, () => []); // unbalanced lines per month
        for (const moveLines of Object.values(moves)) {
            if (isBalanced(moveLines)) {
                const lastChunk = chunks.at(-1);
                if (lastChunk && lastChunk.length + moveLines.length <= maxLines) {
                    lastChunk.push(...moveLines);
                } else {
                    chunks.push(moveLines);
                }
            } else {
                for (const line of moveLines) {
                    const month = getLineMonth(line);
                    unbalancedChunks[month - 1].push(line);
                }
            }
        }

        chunks.push(...unbalancedChunks.filter((chunk) => chunk.length));
        return { header, chunks };
    }

    /**
     * Converts a Base64 encoded string to a Uint8Array.
     * This is more memory efficient than using atob() and charCodeAt()
     * for large strings to avoid causing the browser to crash.
     *
     * @param {string} base64String - The Base64 encoded string to convert.
     * @returns {Uint8Array} The resulting Uint8Array.
     * @throws {Error} If the input string contains invalid Base64 characters.
     */
    function base64ToUint8Array(base64String) {
        const base64Chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

        // Remove any padding
        base64String = base64String.replace(/=+$/, "");

        // Pre-allocate output array
        const outputLength = Math.floor((base64String.length * 6) / 8);
        const output = new Uint8Array(outputLength);

        let bitBuffer = 0;
        let bitsCollected = 0;
        let outputIndex = 0;

        for (let i = 0; i < base64String.length; i++) {
            const charIndex = base64Chars.indexOf(base64String[i]);
            if (charIndex === -1) {
                throw new Error(_t("Invalid Base64 character: %s", base64String[i]));
            }

            bitBuffer = (bitBuffer << 6) | charIndex;
            bitsCollected += 6;

            if (bitsCollected >= 8) {
                bitsCollected -= 8;
                output[outputIndex++] = (bitBuffer >> bitsCollected) & 0xff;
            }
        }

        return output;
    }

    function decodeAttachment(base64String) {
        const bytesData = base64ToUint8Array(base64String);
        const utf8BOM = [0xef, 0xbb, 0xbf]; // BOM for UTF-8

        if (bytesData.length >= 3 && utf8BOM.every((byte, i) => byte === bytesData[i])) {
            // Decode with UTF-8 ignoring BOM
            return new TextDecoder("utf-8").decode(bytesData.slice(3));
        } else {
            // Try different encodings
            const encodings = ["utf-8", "iso-8859-15"];
            for (const encoding of encodings) {
                try {
                    const stringData = new TextDecoder(encoding, { fatal: true }).decode(bytesData);
                    if (stringData) {
                        return stringData;
                    }
                } catch {
                    // Ignore and try next encoding
                }
            }
            throw new Error(_t("Cannot determine the encoding for the attached file."));
        }
    }

    function splitLine(line) {
        return Array.from(line.matchAll(fieldRegex), (part) =>
            // remove double quotes if any
            part[0].replace(/"/g, "").trim()
        );
    }

    function getLineProperty(line, ...properties) {
        for (const property of properties) {
            const value = line[header.indexOf(property)];
            if (value) {
                return value;
            }
        }
        return "";
    }

    function getMoveName(line) {
        return getLineProperty(line, "EcritureNum", "PieceRef");
    }

    function parseFloat(float) {
        // The comma separates the whole fraction from the decimal part.
        // No thousands separator is accepted.
        return Number((float || "0.0").replaceAll(",", "."));
    }

    function isBalanced(moveLines) {
        let balance = 0;
        for (const line of moveLines) {
            const debit = parseFloat(getLineProperty(line, "Debit"));
            const credit = parseFloat(getLineProperty(line, "Credit"));
            balance += debit - credit;
        }

        // debits and credits are in EUR, which has 2 decimal places
        return floatIsZero(balance, 2);
    }

    function getLineMonth(line) {
        const date = getLineProperty(line, "EcritureDate", "PieceDate");
        return parseInt(date.slice(4, 6));
    }

    return { parse };
}
