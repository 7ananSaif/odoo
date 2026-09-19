import { mailModels } from "@mail/../tests/mail_test_helpers";
import { beforeEach, expect, test } from "@odoo/hoot";
import { mockDate, mockTimeZone } from "@odoo/hoot-mock";
import { contains, defineModels, fields, models, mountView } from "@web/../tests/web_test_helpers";

class Partner extends models.Model {
    date = fields.Date({ string: "A date", searchable: true });
    datetime = fields.Datetime({ string: "A datetime", searchable: true });
    _records = [
        {
            id: 1,
            datetime: "2017-02-08 10:00:00",
        },
    ];
}

defineModels({ ...mailModels, Partner });

beforeEach(() => {
    mockTimeZone(+2); // UTC+2
    mockDate("2017-01-25 00:00:00");
});

test("Document datetime in form", async () => {
    await mountView({
        type: "form",
        resModel: "partner",
        resId: 1,
        arch: '<form><field name="datetime" widget="documents_datetime"/></form>',
    });
    expect(
        ".o_field_widget[name=datetime] div[title='A datetime']:contains(02/08/2017)"
    ).toHaveCount(1);
    await contains(".o_field_widget[name=datetime] .fa-edit").click();
    await contains(".o_date_item_cell:contains(27)").click();
    await contains("button:contains(Apply)").click();
    expect(".o_field_widget[name=datetime]:contains(01/27/2017)").toHaveCount(1);
    expect(".o_field_widget[name=datetime]:contains(/)").toHaveCount(1);
    await contains(".o_field_widget[name=datetime] .fa-times").click();
    expect(".o_field_widget[name=datetime]:contains(/)").toHaveCount(0);
});

test("Document datetime and datetime bouton in form", async () => {
    await mountView({
        type: "form",
        resModel: "partner",
        resId: 1,
        arch: `<form>
                    <field name="datetime" widget="documents_datetime" invisible="not datetime"/>
                    <field name="datetime" widget="documents_datetime_btn" invisible="datetime"/>
               </form>`,
    });
    expect(".o_field_documents_datetime[name=datetime]").toHaveCount(1);
    expect(".o_field_documents_datetime_btn[name=datetime]").toHaveCount(0);
    await contains(".o_field_widget[name=datetime] .fa-times").click();
    expect(".o_field_documents_datetime[name=datetime]").toHaveCount(0);
    expect(".o_field_documents_datetime_btn[name=datetime]").toHaveCount(1);
    expect(".o_field_documents_datetime_btn[name=datetime] button").toHaveClass("btn-primary");
    expect(".o_field_documents_datetime_btn[name=datetime] i").toHaveClass("fa-calendar");
});

test("Document datetime bouton options in form", async () => {
    await mountView({
        type: "form",
        resModel: "partner",
        resId: 1,
        arch: `<form>
                    <field name="datetime" widget="documents_datetime_btn"
                        options="{ 'btn_classes': 'btn-secondary', 'icon': 'plus' }"/>
               </form>`,
    });
    expect(".o_field_documents_datetime_btn[name=datetime] i").toHaveClass("fa-plus");
    expect(".o_field_documents_datetime_btn[name=datetime] i").not.toHaveClass("fa-calendar");
    expect(".o_field_documents_datetime_btn[name=datetime] button").toHaveClass("btn-secondary");
    expect(".o_field_documents_datetime_btn[name=datetime] button").not.toHaveClass("btn-primary");
});
