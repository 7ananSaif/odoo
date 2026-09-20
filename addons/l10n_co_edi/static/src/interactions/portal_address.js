import { patch } from '@web/core/utils/patch';
import { patchDynamicContent } from '@web/public/utils';
import { rpc } from '@web/core/network/rpc';
import { CustomerAddress } from '@portal/interactions/address';
import { SelectMenuWrapper } from '@l10n_latam_base/components/select_menu_wrapper/select_menu_wrapper';

patch(CustomerAddress.prototype, {
    setup() {
        super.setup();
        patchDynamicContent(this.dynamicContent, {
            'select[name="l10n_latam_identification_type_id"]': {
                't-on-change': this.onChangeIdentificationType.bind(this),
            },
        });

        this.isColombianCompany = this.countryCode === 'CO';
        this.vat = this.addressForm['o_vat'];
        if (this.isColombianCompany) {
            this.elementCities = this.addressForm.city_id;
            this.elementState = this.addressForm.state_id;
        }
    },

    start() {
        super.start();
        if (!this.isColombianCompany || !this.vat) return;

        const typeSelect = this.el.querySelector('select[name="l10n_co_edi_obligation_type_ids"]');
        this.mountComponent(typeSelect.parentElement, SelectMenuWrapper, { el: typeSelect });
        this.el.querySelector('select[name="l10n_latam_identification_type_id"], input[name="l10n_latam_identification_type_id"]')
            .dispatchEvent(new Event('change'));
    },

    onChangeIdentificationType() {
        if (!this.isColombianCompany || !this.vat) return;

        const selectedIdentificationType = this.addressForm.l10n_latam_identification_type_id
            .selectedOptions[0].text;
        if (selectedIdentificationType === 'NIT') {
            this._showInput('l10n_co_edi_obligation_type_ids');
            this._showInput('l10n_co_edi_fiscal_regimen');
        } else {
            this._hideInput('l10n_co_edi_obligation_type_ids');
            this._hideInput('l10n_co_edi_fiscal_regimen');
        }
    },

    async onChangeState() {
        await this.waitFor(super.onChangeState());
        if (!this.isColombianCompany || this._getSelectedCountryCode() !== 'CO') return;

        const stateId = this.elementState.value;
        let choices = [];
        if (stateId) {
            const data = await this.waitFor(rpc(
                `/portal/l10n_co_state_infos/${this.elementState.value}`, {}
            ));
            choices = data.cities;
        }
        this.elementCities.options.length = 1;
        if (choices.length) {
            choices.forEach((item) => {
                const option = new Option(item[1], item[0]);
                option.setAttribute('data-code', item[2]);
                this.elementCities.appendChild(option);
            });
        }
    },

    async _onChangeCountry(init=false) {
        await this.waitFor(super._onChangeCountry(...arguments));
        if (!this.isColombianCompany) return;

        if (this._getSelectedCountryCode() === 'CO') {
            let cityInput = this.addressForm.city;
            if (cityInput.value) {
                cityInput.value = '';
            }
            this._hideInput('city');
            this._showInput('city_id');
        } else {
            this._hideInput('city_id');
            this._showInput('city');
            this.elementCities.value = '';
        }
    },
});
