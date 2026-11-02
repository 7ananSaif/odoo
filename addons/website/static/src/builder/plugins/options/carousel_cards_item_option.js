import { BaseOptionComponent } from "@html_builder/core/base_option_component";
import { registry } from "@web/core/registry";
import { CardImagePositionOption } from "./card_image_position_option";

export class CarouselCardsItemOption extends BaseOptionComponent {
    static id = "carousel_cards_item_option";
    static template = "website.CarouselCardsItemOption";
    static selector = ".s_carousel_cards_item";
    static applyTo = ":scope > .s_carousel_cards_card";
    static components = {
        CardImagePositionOption,
    };
}

registry.category("website-options").add(CarouselCardsItemOption.id, CarouselCardsItemOption);
