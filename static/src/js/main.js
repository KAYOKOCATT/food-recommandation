/**
 * @file Main JavaScript Entry Point
 * @description Modern ES Module architecture for Django frontend
 * @module main
 */

import { initHTMX } from "./utils/htmx-config.js";
import { logger } from "./utils/logger.js";
import { eventBus } from "./utils/event-bus.js";
import { loginForm } from "./components/alpine-components.js";
import { registerForm } from "./components/register-form.js";

import { Alpine } from "../lib/alpine.esm.js";
import htmx from "../lib/htmx.esm.js";
window.htmx = htmx;

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
 * Initialize the application
 * @returns {Promise<void>}
 */
async function initApp() {
  try {
    logger.info("🚀 Initializing Django Modern Frontend Application");
    // Initialize HTMX configuration
    initHTMX();

    // Set up global event listeners
    setupGlobalListeners();

    // Initialize Alpine.js stores (if needed)
    setupAlpineStores();

    // Register Alpine.js components
    Alpine.data("onMountloginForm", loginForm);
    Alpine.data("registerForm", registerForm);

    logger.success("✅ Application initialized successfully");
  } catch (error) {
    logger.error("❌ Application initialization failed:", error);
  }
}

/**
 * Set up global event listeners
 * @returns {void}
 */
function setupGlobalListeners() {
  // Listen for HTMX events
  document.body.addEventListener("htmx:afterSwap", (event) => {
    logger.debug("HTMX content swapped:", event.detail);
    eventBus.emit("content:updated", event.detail);
  });

  document.body.addEventListener("htmx:responseError", (event) => {
    logger.error("HTMX request failed:", event.detail);
    eventBus.emit("request:error", event.detail);
  });

  // Handle visibility change for performance optimization
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      logger.debug("Page hidden - pausing non-critical tasks");
    } else {
      logger.debug("Page visible - resuming tasks");
    }
  });
}

/**
 * Set up Alpine.js global stores
 * @returns {void}
 */
function setupAlpineStores() {
  Alpine.store("app", {
    version: config.version,
    notifications: [],

    /**
     * Add a notification
     * @param {string} message - Notification message
     * @param {string} type - Notification type (success, error, warning, info)
     */
    addNotification(message, type = "info") {
      const id = Date.now();
      this.notifications.push({ id, message, type });

      // Auto-remove after 5 seconds
      setTimeout(() => {
        this.removeNotification(id);
      }, 5000);
    },

    /**
     * Remove a notification
     * @param {number} id - Notification ID
     */
    removeNotification(id) {
      this.notifications = this.notifications.filter((n) => n.id !== id);
    },
  });

  // Notification store - compatible with existing code
  Alpine.store("notification", {
    notifications: [],

    /**
     * Show a notification
     * @param {string} message - Notification message
     * @param {string} type - Notification type (success, error, warning, info)
     * @param {number} duration - Display duration in milliseconds (default: 5000)
     */
    show(message, type = "info", duration = 5000) {
      const id = Date.now() + Math.random();
      this.notifications.push({ id, message, type });

      logger.info(`Notification [${type}]:`, message);

      // Auto-remove after specified duration
      if (duration > 0) {
        setTimeout(() => {
          this.hide(id);
        }, duration);
      }

      return id;
    },

    /**
     * Hide a notification
     * @param {number} id - Notification ID
     */
    hide(id) {
      this.notifications = this.notifications.filter((n) => n.id !== id);
    },

    /**
     * Clear all notifications
     */
    clear() {
      this.notifications = [];
    },
  });

  logger.debug("Alpine.js stores initialized");
}

// Initialize when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}

// Export config for use in other modules
export { config };
