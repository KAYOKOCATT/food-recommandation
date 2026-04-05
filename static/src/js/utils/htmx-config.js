/**
 * @file HTMX Configuration and Utilities
 * @description Configure HTMX behavior and add custom extensions
 * @module utils/htmx-config
 */

import { logger } from "./logger.js";

/**
 * Initialize HTMX configuration
 * @returns {void}
 */
export function initHTMX() {
  if (typeof htmx === "undefined") {
    logger.warn("HTMX is not loaded");
    return;
  }

  // Configure HTMX
  htmx.config.historyCacheSize = 20;
  htmx.config.timeout = 10000; // 10 seconds
  htmx.config.defaultSwapStyle = "innerHTML";
  htmx.config.scrollBehavior = "smooth";

  // Add custom HTMX event handlers
  setupHTMXEvents();

  logger.debug("HTMX configured successfully");
}

/**
 * Set up HTMX event handlers
 * @returns {void}
 */
function setupHTMXEvents() {
  // Before request - add loading state
  document.body.addEventListener("htmx:beforeRequest", (event) => {
    const target = event.target;
    target.classList.add("htmx-loading");
  });

  // After request - remove loading state
  document.body.addEventListener("htmx:afterRequest", (event) => {
    const target = event.target;
    target.classList.remove("htmx-loading");
  });

  // After swap - scroll to element if needed
  document.body.addEventListener("htmx:afterSwap", (event) => {
    const target = event.target;

    // If target has scroll-to attribute, scroll to it
    if (target.hasAttribute("data-scroll-to")) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });

  // Handle response errors
  document.body.addEventListener("htmx:responseError", (event) => {
    const { xhr } = event.detail;

    logger.error(`HTMX Request Error: ${xhr.status} ${xhr.statusText}`);

    // Show user-friendly error message
    showErrorNotification(`Request failed: ${xhr.statusText}`);
  });

  // Handle timeout
  document.body.addEventListener("htmx:timeout", () => {
    logger.error("HTMX Request Timeout");
    showErrorNotification("Request timed out. Please try again.");
  });
}

/**
 * Show error notification
 * @param {string} message - Error message
 * @returns {void}
 */
function showErrorNotification(message) {
  // Dispatch custom event for notification system
  document.dispatchEvent(
    new CustomEvent("show:notification", {
      detail: { message, type: "error" },
    })
  );
}

/**
 * Trigger HTMX request programmatically
 * @param {HTMLElement} element - Target element
 * @param {string} url - Request URL
 * @param {Object} options - HTMX options
 * @returns {void}
 */
export function triggerHTMXRequest(element, url, options = {}) {
  htmx.ajax("GET", url, {
    target: element,
    swap: "innerHTML",
    ...options,
  });
}

/**
 * Update HTMX element content
 * @param {string} selector - CSS selector
 * @param {string} content - New content
 * @returns {void}
 */
export function updateHTMXContent(selector, content) {
  const element = document.querySelector(selector);
  if (element) {
    element.innerHTML = content;
    htmx.process(element);
  }
}
