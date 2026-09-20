import { user } from "@web/core/user";
import { useBackButton } from "@web_mobile/js/core/hooks";
import { accountMethodsForMobile } from "@web_mobile/js/core/mixins";
import { methods as mobileNativeMethods } from "@web_mobile/js/services/core";
import { Popover } from "@web/core/popover/popover";
import {
    clickSave,
    contains,
    defineModels,
    fields,
    models,
    mountView,
    mountWithCleanup,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { animationFrame } from "@odoo/hoot-mock";
import { destroy, getFixture, expect, test } from "@odoo/hoot";
import { Component, useState, xml } from "@odoo/owl";

const MY_IMAGE =
    "iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4//8/w38GIAXDIBKE0DHxgljNBAAO9TXL0Y4OHwAAAABJRU5ErkJggg==";
const BASE64_SVG_IMAGE =
    "PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPScxNzUnIGhlaWdodD0nMTAwJyBmaWxsPScjMDAwJz48cG9seWdvbiBwb2ludHM9JzAsMCAxMDAsMCA1MCw1MCcvPjwvc3ZnPg==";
const BASE64_PNG_HEADER = "iVBORw0KGg";

class Users extends models.Model {
    name = fields.Char();
}

defineModels([Users]);

test("component should receive a backbutton event", async () => {
    patchWithCleanup(mobileNativeMethods, {
        overrideBackButton({ enabled }) {
            expect.step(`overrideBackButton: ${enabled}`);
        },
    });

    class DummyComponent extends Component {
        static template = xml`<div/>`;
        static props = ["*"];

        setup() {
            useBackButton(this._onBackButton);
        }

        _onBackButton(ev) {
            expect.step(`${ev.type} event`);
        }
    }

    const dummy = await mountWithCleanup(DummyComponent);
    // simulate 'backbutton' event triggered by the app
    document.dispatchEvent(new Event("backbutton"));
    expect.verifySteps(["overrideBackButton: true", "backbutton event"]);
    destroy(dummy);
    expect.verifySteps(["overrideBackButton: false"]);
});

test("multiple components should receive backbutton events in the right order", async () => {
    patchWithCleanup(mobileNativeMethods, {
        overrideBackButton({ enabled }) {
            expect.step(`overrideBackButton: ${enabled}`);
        },
    });

    class DummyComponent extends Component {
        static template = xml`<div/>`;
        static props = ["*"];
        setup() {
            useBackButton(this._onBackButton);
        }

        _onBackButton(ev) {
            expect.step(`${this.props.name}: ${ev.type} event`);
            // unmounting is not supported anymore
            // A real business case equivalent to this is to have a Parent component
            // doing a foreach on some reactive object which contains the list of dummy components
            // and calling a callback props.onBackButton right here that removes the element from the list
            destroy(this);
        }
    }

    await mountWithCleanup(DummyComponent, { props: { name: "dummy1" } });
    await mountWithCleanup(DummyComponent, { props: { name: "dummy2" } });
    await mountWithCleanup(DummyComponent, { props: { name: "dummy3" } });

    // simulate 'backbutton' events triggered by the app
    document.dispatchEvent(new Event("backbutton"));
    document.dispatchEvent(new Event("backbutton"));
    document.dispatchEvent(new Event("backbutton"));

    expect.verifySteps([
        "overrideBackButton: true",
        "dummy3: backbutton event",
        "dummy2: backbutton event",
        "dummy1: backbutton event",
        "overrideBackButton: false",
    ]);
});

test("component should receive a backbutton event: custom activation", async () => {
    patchWithCleanup(mobileNativeMethods, {
        overrideBackButton({ enabled }) {
            expect.step(`overrideBackButton: ${enabled}`);
        },
    });

    class DummyComponent extends Component {
        static template = xml`<button class="dummy" t-esc="state.show" t-on-click="toggle"/>`;
        static props = ["*"];
        setup() {
            this._backButtonHandler = useBackButton(
                this._onBackButton,
                this.shouldActivateBackButton.bind(this)
            );
            this.state = useState({
                show: this.props.show,
            });
        }

        toggle() {
            this.state.show = !this.state.show;
        }

        shouldActivateBackButton() {
            return this.state.show;
        }

        _onBackButton(ev) {
            expect.step(`${ev.type} event`);
        }
    }

    const dummy = await mountWithCleanup(DummyComponent, { props: { show: false } });
    // shouldn't have enabled back button mount
    expect.verifySteps([]);
    await contains(".dummy").click();
    // simulate 'backbutton' event triggered by the app
    document.dispatchEvent(new Event("backbutton"));
    await contains(".dummy").click();
    // should have enabled/disabled the back button override
    expect.verifySteps([
        "overrideBackButton: true",
        "backbutton event",
        "overrideBackButton: false",
    ]);
    destroy(dummy);

    // enabled at mount
    const dummy2 = await mountWithCleanup(DummyComponent, { props: { show: true } });
    // shouldn't have enabled back button at mount
    expect.verifySteps(["overrideBackButton: true"]);
    // simulate 'backbutton' event triggered by the app
    document.dispatchEvent(new Event("backbutton"));
    destroy(dummy2);
    // should have disabled the back-button override during unmount
    expect.verifySteps(["backbutton event", "overrideBackButton: false"]);
});

test("popover is closable with backbutton event", async () => {
    patchWithCleanup(mobileNativeMethods, {
        overrideBackButton({ enabled }) {
            expect.step(`overrideBackButton: ${enabled}`);
        },
    });
    class Comp extends Component {
        static template = xml`<div id="comp">in popover</div>`;
        static props = ["*"];
    }
    const pop = await mountWithCleanup(Popover, {
        props: {
            target: getFixture(),
            position: "bottom",
            component: Comp,
            close: () => destroy(pop),
        },
    });
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover #comp").toHaveCount(1);
    expect.verifySteps(["overrideBackButton: true"]);
    // simulate 'backbutton' event triggered by the app
    document.dispatchEvent(new Event("backbutton"));

    expect.verifySteps(["overrideBackButton: false"]);

    expect(".o_popover").toHaveCount(0);
    expect(".o_popover #comp").toHaveCount(0);
});

test("controller should call native updateAccount method with SVG avatar when saving record", async () => {
    patchWithCleanup(mobileNativeMethods, {
        updateAccount(options) {
            const { avatar, name, username } = options;
            expect.step("should call updateAccount");
            expect(avatar.startsWith(BASE64_PNG_HEADER)).toBe(true, {
                message: "should have a PNG base64 encoded avatar",
            });
            expect(name).toBe("Marc Demo");
            expect(username).toBe("demo");
        },
    });

    patchWithCleanup(user, { login: "demo", name: "Marc Demo" });

    patchWithCleanup(accountMethodsForMobile, {
        url(path) {
            if (path === "/web/image") {
                return `data:image/svg+xml;base64,${BASE64_SVG_IMAGE}`;
            }
            return super.url(...arguments);
        },
    });

    await mountView({
        type: "form",
        resModel: "users",
        arch: `
            <form js_class="res_users_preferences_form">
                <sheet>
                    <field name="name"/>
                </sheet>
            </form>`,
    });

    await clickSave();
    expect.verifySteps(["should call updateAccount"]);
});

test("controller should call native updateAccount method when saving record", async () => {
    patchWithCleanup(mobileNativeMethods, {
        async updateAccount(options) {
            const { avatar, name, username } = options;
            expect.step("should call updateAccount");
            expect(avatar.startsWith(BASE64_PNG_HEADER)).toBe(true, {
                message: "should have a PNG base64 encoded avatar",
            });
            expect(name).toBe("Marc Demo");
            expect(username).toBe("demo");
        },
    });
    patchWithCleanup(user, { login: "demo", name: "Marc Demo" });
    patchWithCleanup(accountMethodsForMobile, {
        url(path) {
            if (path === "/web/image") {
                return `data:image/png;base64,${MY_IMAGE}`;
            }
            return super.url(...arguments);
        },
    });

    await mountView({
        type: "form",
        resModel: "users",
        arch: `
            <form js_class="res_users_preferences_form">
                <sheet>
                    <field name="name"/>
                </sheet>
            </form>`,
    });

    await clickSave();
    expect.verifySteps(["should call updateAccount"]);
});
