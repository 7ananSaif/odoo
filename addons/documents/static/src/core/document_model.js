export class Document {
    id;
    /** @type {import("models").Attachment} */
    attachment;
    /** @type {string} */
    name;
    /** @type {string} */
    mimetype;
    /** @type {string} */
    url;
    /** @type {string} */
    displayName;
    /** @type {Object} */
    record;
    /** @type {import("models").Store} */
    store;
}
