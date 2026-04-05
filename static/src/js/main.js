/**
 * @file Main JavaScript Entry Point
 * @description Modern ES Module architecture for Django frontend
 * @module main
 *
 * LOADING ORDER (IMPORTANT):
 * 1. This file loads first (type="module", blocking)
 * 2. It adds listener for 'alpine:init' event
 * 3. Alpine CDN loads with defer
 * 4. Alpine fires 'alpine:init', we register components
 * 5. Alpine starts and scans DOM for x-data
 */

import { initHTMX } from "./utils/htmx-config.js";
import { logger } from "./utils/logger.js";
import { eventBus } from "./utils/event-bus.js";
import { loginForm } from "./components/alpine-components.js";
import { registerForm } from "./components/register-form.js";

/**
 * Application configuration
 * @typedef {Object} AppConfig
 * @property {boolean} debug - Debug mode flag
 * @property {string} version - Application version
 * @property {string} apiBaseUrl - Base URL for API calls
 */

/** @type {AppConfig} */
const config = {
  debug: true,
  version: "1.0.0",
  apiBaseUrl: "/api/v1",
};

/**
 * Register Alpine components - called during alpine:init
 * This runs BEFORE Alpine scans the DOM
 */
function setupAlpineComponents() {
  // Get Alpine from window (injected by CDN)
  const Alpine = window.Alpine;

  if (!Alpine) {
    logger.error("Alpine not found on window during alpine:init");
    return;
  }

  // Initialize stores first
  Alpine.store("app", {
    version: config.version,
    notifications: [],

    addNotification(message, type = "info") {
      const id = Date.now();
      this.notifications.push({ id, message, type });
      setTimeout(() => {
        this.removeNotification(id);
      }, 5000);
    },

    removeNotification(id) {
      this.notifications = this.notifications.filter((n) => n.id !== id);
    },
  });

  Alpine.store("notification", {
    notifications: [],

    show(message, type = "info", duration = 5000) {
      const id = Date.now() + Math.random();
      this.notifications.push({ id, message, type });
      logger.info(`Notification [${type}]:`, message);
      if (duration > 0) {
        setTimeout(() => this.hide(id), duration);
      }
      return id;
    },

    hide(id) {
      this.notifications = this.notifications.filter((n) => n.id !== id);
    },

    clear() {
      this.notifications = [];
    },
  });

  // Register data components
  Alpine.data("loginForm", loginForm);
  Alpine.data("registerForm", registerForm);

  logger.success("Alpine components and stores registered");
}

/**
 * Set up global event listeners
 */
function setupGlobalListeners() {
  // HTMX events
  document.body.addEventListener("htmx:afterSwap", (event) => {
    logger.debug("HTMX content swapped:", event.detail);
    eventBus.emit("content:updated", event.detail);
  });

  document.body.addEventListener("htmx:responseError", (event) => {
    logger.error("HTMX request failed:", event.detail);
    eventBus.emit("request:error", event.detail);
  });
}

/**
 * Initialize application
 */
(function init() {
  logger.info("🚀 Initializing application...");

  // Init HTMX config
  initHTMX();

  // Set up global listeners
  setupGlobalListeners();

  // Register Alpine components BEFORE Alpine loads
  // This listener will fire when Alpine CDN script executes
  document.addEventListener("alpine:init", () => {
    logger.info("alpine:init fired - registering components");
    setupAlpineComponents();
  });

  logger.success("✅ Application initialized, waiting for Alpine...");
})();

// Export for other modules
export { config };
