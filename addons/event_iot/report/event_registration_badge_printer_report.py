import io

from odoo import api, models
from odoo.tools import float_compare

from base64 import b64decode
from markupsafe import Markup
from PIL import Image
from typing import Literal, Optional


class EventRegistrationBadgePrinterReport(models.AbstractModel):
    _name = 'report.event_iot.event_registration_badge_printer_report'
    _description = 'ESC/Label Event Badge'

    @api.model
    def load_image(
        self,
        image_field: str,
        size: Optional[tuple[int, int]] = None,
        crop_mode: Literal["contain", "cover"] = "contain",
        flip=False
    ):
        """
        Saves an image to the printer under the name `{filename}.PNG`.

        If `size` is specified, the image is resized first.
        The resizing behaviour is determined by `crop_mode`:
        - `"contain"`: Add transparent padding if needed
        - `"cover"`: Crop original image if needed

        If `flip` is `True`, the image is rotated 180° before uploading.
        """
        if not image_field:
            return None

        image_data = b64decode(image_field)
        image_buffer = io.BytesIO(image_data)
        image = Image.open(image_buffer)

        if flip:
            image = image.rotate(180)

        if size:
            target_width, target_height = size
            source_aspect = image.width / image.height
            target_aspect = target_width / target_height

            if float_compare(source_aspect, target_aspect, 2) == 0:
                image = image.resize(size=size)
            elif crop_mode == "cover":
                if target_aspect >= source_aspect:
                    crop_amount = int((image.height - (image.width / target_aspect)) / 2)
                else:
                    crop_amount = int((image.width - (image.height * target_aspect)) / 2)
                source_rect = (
                    (0, crop_amount, image.width, image.height - crop_amount)
                    if target_aspect >= source_aspect
                    else (crop_amount, 0, image.width - crop_amount, image.height)
                )
                image = image.resize(size=size, box=source_rect)
            elif crop_mode == "contain":
                container_image = Image.new("RGBA", size=size, color="#0000")
                if target_aspect >= source_aspect:
                    new_width = int(target_height * source_aspect)
                    padding_amount = int((target_width - new_width) / 2)
                    image = image.resize(size=(new_width, target_height))
                    container_image.paste(image, (padding_amount, 0))
                else:
                    new_height = int(target_width / source_aspect)
                    padding_amount = int((target_height - new_height) / 2)
                    image = image.resize(size=(target_width, new_height))
                    container_image.paste(image, (0, padding_amount))
                image = container_image

        png_buffer = io.BytesIO()
        image.save(png_buffer, format="PNG")
        return png_buffer.getvalue()

    @api.model
    def escape(self, text: str):
        """
        Escapes text to be safe for the ESC/Label format.
        You must precede the ^FD command with ^FH to enable escaping.
        """
        return Markup(text).replace("_", "_5f").replace("^", "_5e")

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['event.registration'].browse(docids)

        return {
            'docs': docs,
            'escape': self.escape,
            'load_image': self.load_image,
        }
