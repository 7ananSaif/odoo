import { Box } from '@iap_extract/components/manual_correction/box';
import { Component, useExternalListener, useRef, useState } from "@odoo/owl";

export class BoxLayer extends Component {
    static components = { Box };
    static template = "iap_extract.BoxLayer";
    static props = {
        boxes: Array,
        pageLayer: {
            validate: (pageLayer) => {
                // target may be inside an iframe, so get the Element constructor
                // to test against from its owner document's default view
                const Element = pageLayer?.ownerDocument?.defaultView?.Element;
                return (
                    (Boolean(Element) &&
                        (pageLayer instanceof Element || pageLayer instanceof window.Element)) ||
                    (typeof pageLayer === "object" && pageLayer?.constructor?.name?.endsWith("Element"))
                );
            },
        },
        onClickBoxCallback: Function,
        onBoxesSelectionCallback: Function,
        mode: String,
    };
    /**
     * @override
     */
    setup() {
        this.state = useState({
            boxes: this.props.boxes,
            isSelecting: false,
            selectionStart: { x: 0, y: 0 },
            selectionEnd: { x: 0, y: 0 },
        });
        this.boxLayerRef = useRef("boxLayer");

        // Used to define the style of the contained boxes
        if (this.isOnPDF) {
            this.pageWidth = this.props.pageLayer.style.width;
            this.pageHeight = this.props.pageLayer.style.height;

            // Get the scrollable element of the PDF viewer to listen to scroll events
            this.viewerScrollableEl = this.props.pageLayer.ownerDocument.getElementById("viewerContainer");
            useExternalListener(this.viewerScrollableEl, "scroll", this.onScroll);
        } else if (this.isOnImg) {
            this.viewerScrollableEl = this.props.pageLayer.parentElement;
            useExternalListener(this.viewerScrollableEl, "scroll", this.onScroll);
            this.pageWidth = `${this.props.pageLayer.clientWidth}px`;
            this.pageHeight = `${this.props.pageLayer.clientHeight}px`;
        }
    }

    checkAndHighlightBoxes() {
        const { selectionStart, selectionEnd } = this.state;
        const selectionRect = {
            left: Math.min(selectionStart.x, selectionEnd.x),
            top: Math.min(selectionStart.y, selectionEnd.y),
            right: Math.max(selectionStart.x, selectionEnd.x),
            bottom: Math.max(selectionStart.y, selectionEnd.y),
        };

        const boxElements = this.boxLayerRef.el.querySelectorAll('.o_extract_mixin_box');

        boxElements.forEach(boxEl => {
            const boxId = parseInt(boxEl.dataset.id, 10);
            const matchedBox = this.props.boxes.find(box => box.id === boxId);
            const boxRect = boxEl.getBoundingClientRect();

            const isOverlapping = !(
                boxRect.right < selectionRect.left ||
                boxRect.left > selectionRect.right ||
                boxRect.bottom < selectionRect.top ||
                boxRect.top > selectionRect.bottom
            );
            matchedBox.isHighlighted = isOverlapping;
        });
    }

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    get style() {
        if (this.isOnPDF) {
            return 'width: ' + this.props.pageLayer.style.width + '; ' +
                   'height: ' + this.props.pageLayer.style.height + ';';
        } else if (this.isOnImg) {
            return 'width: ' + this.props.pageLayer.clientWidth + 'px; ' +
                   'height: ' + this.props.pageLayer.clientHeight + 'px; ' +
                   'left: ' + this.props.pageLayer.offsetLeft + 'px; ' +
                   'top: ' + this.props.pageLayer.offsetTop + 'px;';
        }
    }

    get selectionStyle() {
        const { selectionStart, selectionEnd } = this.state;
        const x1 = Math.min(selectionStart.x, selectionEnd.x);
        const y1 = Math.min(selectionStart.y, selectionEnd.y);
        const x2 = Math.max(selectionStart.x, selectionEnd.x);
        const y2 = Math.max(selectionStart.y, selectionEnd.y);

        return `
            left: ${x1}px;
            top: ${y1}px;
            width: ${x2 - x1}px;
            height: ${y2 - y1}px;
        `;
    }

    get isOnImg() {
        return this.props.mode === 'img';
    }

    get isOnPDF() {
        return this.props.mode === 'pdf';
    }

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    onMouseDown(event) {
        this.state.isSelecting = true;
        this.state.selectionStart = { x: event.clientX, y: event.clientY};
        this.state.selectionEnd = { x: event.clientX, y: event.clientY};
        if (this.viewerScrollableEl) {
            this.scrollX = this.viewerScrollableEl.scrollLeft;
            this.scrollY = this.viewerScrollableEl.scrollTop;
        }
    }

    onMouseUp(event) {
        if (!this.state.isSelecting) {
            return;
        }

        this.state.isSelecting = false;

        this.checkAndHighlightBoxes();

        const selectedBoxes = this.props.boxes.filter(box => box.isHighlighted);
        this.props.onBoxesSelectionCallback(selectedBoxes);

        this.props.boxes.forEach(box => box.isHighlighted = false);
        this.state.selectionStart = { x: 0, y: 0 };
        this.state.selectionEnd = { x: 0, y: 0 };
    }

    onMouseMove(event) {
        if (!this.state.isSelecting) {
            return;
        }
        this.state.selectionEnd = { x: event.clientX, y: event.clientY };
        this.checkAndHighlightBoxes();
    }

    onScroll(event) {
        if (this.state.isSelecting) {
            // Adjust the selection on scroll
            const scrollX = this.viewerScrollableEl.scrollLeft;
            const scrollY = this.viewerScrollableEl.scrollTop;

            this.state.selectionStart.x += this.scrollX - scrollX;
            this.state.selectionStart.y += this.scrollY - scrollY;

            this.scrollX = scrollX;
            this.scrollY = scrollY;
        }
    }
};
