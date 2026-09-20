import { setRecurringAnimationFrame, debounce } from "@web/core/utils/timing";
const MIN_ID = -(2 ** 30);

/**
 * Adds helper lines to the document
 *
 * @param {HTMLElement} target
 * @returns {Object} helpers
 * @returns {Function} helpers.show shows the helper lines at a certain sign item
 * @returns {Function} helpers.hide hides the helper lines
 */
export function startHelperLines(target) {
    function showHelperLinesAt(signItem, coords) {
        const calculate = {
            left: (pos) => ({ left: `${pos.left}px` }),
            right: (pos) => ({ left: `${pos.left + pos.width}px` }),
            top: (pos) => ({ top: `${pos.top}px` }),
            bottom: (pos) => ({ top: `${pos.top + pos.height}px` }),
        };

        const rect = signItem.getBoundingClientRect();
        const positions = {
            top: (coords && coords.y) || rect.top,
            left: (coords && coords.x) || rect.left,
            height: signItem.clientHeight,
            width: signItem.clientWidth,
        };
        for (const line in helperLines) {
            const newPos = calculate[line](positions);
            Object.assign(helperLines[line].style, {
                visibility: "visible",
                ...newPos,
            });
        }
    }

    function hideHelperLines() {
        for (const line in helperLines) {
            helperLines[line].style.visibility = "hidden";
        }
    }

    const top = target.createElement("div");
    const bottom = target.createElement("div");
    top.className = "o_sign_drag_helper o_sign_drag_top_helper";
    bottom.className = "o_sign_drag_helper o_sign_drag_top_helper";
    const left = target.createElement("div");
    const right = target.createElement("div");
    left.className = "o_sign_drag_helper o_sign_drag_side_helper";
    right.className = "o_sign_drag_helper o_sign_drag_side_helper";

    const body = target.querySelector("body");
    body.appendChild(top);
    body.appendChild(bottom);
    body.appendChild(left);
    body.appendChild(right);

    const helperLines = {
        top,
        bottom,
        left,
        right,
    };

    return {
        show: showHelperLinesAt,
        hide: hideHelperLines,
    };
}

export function isVisible(e) {
    return e && !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
}

export function offset(el) {
    const box = el.getBoundingClientRect();
    const docElem = document.documentElement;
    return {
        top: box.top + window.scrollY - docElem.clientTop,
        left: box.left + window.scrollY - docElem.clientLeft,
    };
}

/**
 * Normalizes the normalize position of a sign item to prevent dropping outside the page
 * @param {Number} position x/y position
 * @param {Number} itemDimension size of item at x/y direction
 * @returns {Number}
 */
export function normalizePosition(position, itemDimension) {
    if (position < 0) {
        return 0;
    } else if (position + itemDimension > 1.0) {
        return 1.0 - itemDimension;
    }
    return position;
}

/**
 * Normalizes the new dimension of a sign item to prevent it from resizing outside the page
 * @param {Number} dimension
 * @param {Number} position
 * @returns {Number} normalized dimension
 */
export function normalizeDimension(dimension, position) {
    if (position + dimension > 1) {
        return 1 - position;
    }
    return dimension;
}

/**
 * Generates a random negative ID to be added to sign items that were just created and are not in the DB yet
 * @returns {Number}
 */
export function generateRandomId() {
    return Math.floor(Math.random() * MIN_ID) - 1;
}

/**
 * Adds smooth scrolling while dragging elements
 * @param {HTMLElement} container the container that sets the reference for scrolling
 * @param {HTMLElement} element the element being dragged
 * @param {HTMLElement || null} dragImageElement in some cases the element being dragged is not the same size as the dragImageElement
 * @param {HelperLines} helperLines instance of helper lines for guiding the user while dragging
 * @returns {Function} cleanup function to be executed when dragging is over
 */
export function startSmoothScroll(container, element, dragImageElement = null, helperLines, offsetX = 0, offsetY = 0) {
    const boundary = 0.2;
    const directions = {
        up: -1,
        down: 1,
        left: -1,
        right: 1,
    };
    const mouse = {};
    const containerOffset = offset(container);
    const dragAmount = 10;
    const el = dragImageElement || element;
    function updateMousePosition(e) {
        // calculates the event's position relative to the container
        mouse.x = e.clientX - containerOffset.left - offsetX;
        mouse.y = e.clientY - containerOffset.top - offsetY;
        helperLines.show(el, { x: e.clientX - offsetX, y: e.clientY - offsetY });
    }
    const debouncedOnMouseMove = debounce(updateMousePosition, "animationFrame", true);
    container.addEventListener("dragover", debouncedOnMouseMove);
    const cleanup = setRecurringAnimationFrame(() => {
        const { x, y } = mouse;
        let scrollX,
            scrollY = 0;
        if (x <= container.clientWidth * boundary) {
            scrollX = directions.left * dragAmount;
        } else if (x >= container.clientWidth * (1 - boundary)) {
            scrollX = directions.right * dragAmount;
        }

        if (y <= container.clientHeight * boundary) {
            scrollY = directions.up * dragAmount;
        } else if (y >= container.clientHeight * (1 - boundary)) {
            scrollY = directions.down * dragAmount;
        }
        container.scrollBy(scrollX, scrollY);
    });
    return () => {
        cleanup();
        container.removeEventListener("dragover", debouncedOnMouseMove);
        helperLines.hide();
    };
}

/**
 * Adds resizing functionality to a sign item
 * @param {SignItem} signItem
 * @param {Function} onResize
 */
export function startResize(signItem, onResize) {
    const page = signItem.el.parentElement;
    const mouse = {};
    const resizeHandleWidth = signItem.el.querySelector(".resize_width");
    const resizeHandleHeight = signItem.el.querySelector(".resize_height");
    const resizeHandleBoth = signItem.el.querySelector(".resize_both");

    const computeDimensions = (e) => {
        const { direction, x, y } = mouse;
        const computedStyle = getComputedStyle(signItem.el);
        const signItemAbsoluteWidth = parseInt(computedStyle.width);
        const signItemAbsoluteHeight = parseInt(computedStyle.height);
        const dX = e.clientX - x;
        const dY = e.clientY - y;

        Object.assign(mouse, {
            x: e.clientX,
            y: e.clientY,
        });

        const factor = {
            x: (dX + signItemAbsoluteWidth) / signItemAbsoluteWidth,
            y: (dY + signItemAbsoluteHeight) / signItemAbsoluteHeight,
        };

        if (dX < 0 && Math.abs(dX) >= signItemAbsoluteWidth) {
            factor.x = 1;
        }

        if (dY < 0 && Math.abs(dY) >= signItemAbsoluteHeight) {
            factor.y = 1;
        }

        const width =
            direction === "width" || direction === "both"
                ? Math.round(
                      normalizeDimension(factor.x * signItem.data.width, signItem.data.posX) * 1000
                ) / 1000
                : signItem.data.width;

        const height =
            direction === "height" || direction === "both"
                ? Math.round(
                      normalizeDimension(factor.y * signItem.data.height, signItem.data.posY) * 1000
                ) / 1000
                : signItem.data.height;

        return { height, width };
    };

    const handleMouseMove = (e) => {
        if (signItem.el.classList.contains("o_resizing")) {
            e.preventDefault();
            onResize(signItem, computeDimensions(e), false);
        }
    };

    const debouncedOnMouseMove = debounce(handleMouseMove, "animationFrame", true);
    const handleMouseDown = (e, direction) => {
        e.preventDefault();
        signItem.el.classList.add("o_resizing");
        Object.assign(mouse, { x: e.clientX, y: e.clientY, direction });
        page.addEventListener("mousemove", debouncedOnMouseMove);
    };

    resizeHandleWidth.addEventListener("mousedown", (e) => handleMouseDown(e, "width"));
    resizeHandleHeight.addEventListener("mousedown", (e) => handleMouseDown(e, "height"));
    resizeHandleBoth.addEventListener("mousedown", (e) => handleMouseDown(e, "both"));

    page.addEventListener("mouseup", (e) => {
        if (signItem.el.classList.contains("o_resizing")) {
            signItem.el.classList.remove("o_resizing");
            page.removeEventListener("mousemove", debouncedOnMouseMove);
            onResize(signItem, computeDimensions(e), true);
        }
    });
}

/**
 * Generates the PDF.JS URL from the attachment location
 * @param { String } attachmentLocation
 * @param { Boolean } isSmall
 * @returns
 */
export function buildPDFViewerURL(attachmentLocation, isSmall) {
    const date = new Date().toISOString();
    const baseURL = "/web/static/lib/pdfjs/web/viewer.html";
    // encodes single quote and double quotes as encodeURIComponent does not handle those
    attachmentLocation = encodeURIComponent(attachmentLocation)
        .replace(/'/g, "%27")
        .replace(/"/g, "%22");
    const zoom = isSmall ? "page-fit" : "page-width";
    return `${baseURL}?unique=${date}&file=${attachmentLocation}#page=1&zoom=${zoom}&pagemode=none`;
}

export function injectPDFCustomStyles(iframeDoc) {
    /* Apply custom styles for documents's PDF viewers as early as possible
    to minimize the visibility of default PDF.js styles during rendering. */
    const link = iframeDoc.createElement('link');
    link.rel = 'stylesheet';
    link.type = 'text/css';
    link.href = '/sign/static/src/css/pdfjs_overrides.css';
    iframeDoc.head.appendChild(link);
}


/**
 * Adds auto-scrolling functionality when mouse is near container top/bottom edges
 * @param {HTMLElement} container the container that sets the reference for scrolling
 * @param {Object} mousePosition relative x,y coordinates within container
 * @param {Number} boundary percentage of container edge that triggers scrolling (default 0.2 = 20%)
 * @param {Number} maxDragAmount maximum pixels to scroll per frame (default 80)
 * @returns {Number} scrollY amount to scroll
 */
export function getAutoScrollOffset(container, mousePosition, boundary = 0.2, maxDragAmount = 200) {
    let isScrolling = false;
    let scrollCleanup = null;

    /**
     * Calculates the scroll amount based on the mouse position
     * @param {Object} pos - The mouse position
     * @param {number} pos.y - The y coordinate of the mouse position
     * @returns {number} The scroll amount
     */
    function calculateScrollAmount(pos) {
        let scrollY = 0;
        const boundaryPixels = container.clientHeight * boundary;
        if (pos.y <= boundaryPixels) {
            const distance = pos.y;
            const factor = 1 - (distance / boundaryPixels);
            scrollY = -Math.round(maxDragAmount * factor);
        } else if (pos.y >= container.clientHeight * (1 - boundary)) {
            const distance = container.clientHeight - pos.y;
            const factor = 1 - (distance / boundaryPixels);
            scrollY = Math.round(maxDragAmount * factor);
        }
        return scrollY;
    }

    /**
     * Starts the auto-scrolling animation
     * @param {Object} pos - The mouse position
     * @param {number} pos.y - The y coordinate of the mouse position
     */
    function startScrolling(pos) {
        if (isScrolling) {
            return;
        }
        isScrolling = true;
        scrollCleanup = setRecurringAnimationFrame(() => {
            const scrollAmount = calculateScrollAmount(pos);
            if (scrollAmount !== 0) {
                container.scrollBy(0, scrollAmount);
            } else {
                stopScrolling();
            }
        });
    }

    /**
     * Stops the auto-scrolling animation
     */
    function stopScrolling() {
        if (scrollCleanup) {
            scrollCleanup();
            scrollCleanup = null;
        }
        isScrolling = false;
    }

    /**
     * Updates the position of the mouse and starts the auto-scrolling animation if necessary
     * @param {Object} pos - The mouse position
     * @param {number} pos.y - The y coordinate of the mouse position
     */
    function updatePosition(pos) {
        const scrollAmount = calculateScrollAmount(pos);
        if (scrollAmount !== 0) {
            startScrolling(pos);
        } else {
            stopScrolling();
        }
    }
    updatePosition(mousePosition);
    return {
        updatePosition,
        stopScrolling,
    };
}
