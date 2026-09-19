import { fields, models } from "@web/../tests/web_test_helpers";

export class ExtractMixinWithWordsModel extends models.ServerModel {
    _name = "extract.mixin.with.words";
}

export class ManualCorrectionModel extends models.Model {
    _name = "iap_extract.manual.correction";
    _inherit = ["extract.mixin.with.words"];

    char_field = fields.Char();
    text_field = fields.Text();
    html_field = fields.Html();
    integer_field = fields.Integer();
    float_field = fields.Float();
    monetary_field = fields.Monetary({ currency_field: "currency_id" });
    date_field = fields.Date();
    datetime_field = fields.Datetime()
    currency_id = fields.Many2one({ relation: "res.currency" });
    partner_id = fields.Many2one({ relation: "res.partner" });

    line_ids = fields.One2many({ relation: "iap_extract.manual.correction.line" });
}

export class ManualCorrectionLineModel extends models.Model {
    _name = "iap_extract.manual.correction.line";

    char_field = fields.Char();
    float_field = fields.Float();
    date_field = fields.Date();
}
