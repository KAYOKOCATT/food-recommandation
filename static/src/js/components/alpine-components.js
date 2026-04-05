/**
 * @file Alpine.js Reusable Components
 * @description Modular Alpine.js components for form handling
 * @module components/alpine-components
 */

import { config } from "../main.js";
import { validateForm, getValidationMessage } from "../utils/formValidation.js";
import { post } from "../utils/http.js";
import { logger } from "../utils/logger.js";

// NOTE: Don't cache Alpine at module load time - it may not be loaded yet
// Access window.Alpine at runtime instead

/**
 * Base Form Component
 * Provides common form handling functionality
 *
 * @param {Object} config - Component configuration
 * @param {Object} config.initialData - Initial form data
 * @param {Object} config.validationRules - Validation rules for fields
 * @param {string} config.submitUrl - Form submission URL
 * @param {Function} config.onSuccess - Success callback
 * @param {Function} config.onError - Error callback
 * @returns {Object} Alpine.js component
 */
export function createFormComponent(config) {
  const {
    initialData = {},
    validationRules = {},
    submitUrl = "",
    onSuccess = null,
    onError = null,
  } = config;

  return {
    // Form data
    formData: { ...initialData },

    // Error messages
    errors: {},

    // Submission state
    isSubmitting: false,

    /**
     * Initialize component
     */
    init() {
      logger.debug("Form component initialized", {
        initialData,
        validationRules,
      });
    },

    /**
     * Validate a single field
     * @param {string} field - Field name
     * @returns {boolean} Validation result
     */
    validateField(field) {
      const rules = validationRules[field];
      if (!rules) return true;

      const value = this.formData[field];
      this.errors[field] = "";

      // Use the validation utility
      const result = validateForm({ [field]: value }, { [field]: rules });

      if (!result.valid) {
        this.errors[field] = result.errors[field];
        return false;
      }

      return true;
    },

    /**
     * Validate entire form
     * @returns {boolean} Validation result
     */
    validateForm() {
      const result = validateForm(this.formData, validationRules);
      this.errors = { ...result.errors };
      return result.valid;
    },

    /**
     * Clear field error
     * @param {string} field - Field name
     */
    clearError(field) {
      this.errors[field] = "";
    },

    /**
     * Reset form
     */
    resetForm() {
      this.formData = { ...initialData };
      this.errors = {};
      this.isSubmitting = false;
    },

    /**
     * Handle form submission
     * @param {Event} event - Form event
     */
    async handleSubmit(event) {
      event?.preventDefault();

      // Validate form
      if (!this.validateForm()) {
        logger.warn("Form validation failed", this.errors);
        return;
      }

      this.isSubmitting = true;

      try {
        logger.info("Submitting form", { url: submitUrl });
        const response = await post(submitUrl, this.formData);

        logger.success("Form submitted successfully", response);

        // Call success callback
        if (onSuccess) {
          await onSuccess.call(this, response);
        }
      } catch (error) {
        logger.error("Form submission failed", error);

        // Call error callback
        if (onError) {
          await onError.call(this, error);
        } else {
          // Default error handling
          this.handleError(error);
        }
      } finally {
        this.isSubmitting = false;
      }
    },

    /**
     * Handle submission error
     * @param {Error} error - Error object
     */
    handleError(error) {
      if (error.data && typeof error.data === "object") {
        // Map backend errors to form fields
        Object.keys(error.data).forEach((key) => {
          if (key in this.formData) {
            this.errors[key] = error.data[key];
          }
        });
      }

      // Show notification if available
      const Alpine = window.Alpine;
      if (Alpine?.store("notification")) {
        const message =
          error.data?.error || error.message || "Submission failed";
        Alpine.store("notification").show(message, "error");
      }
    },
  };
}

/**
 * Login Form Component
 * Specialized component for login functionality
 *
 * @returns {Object} Alpine.js component
 */
export function loginForm() {
  return createFormComponent({
    initialData: {
      username: "",
      password: "",
      remember: false,
    },

    validationRules: {
      username: ["required", "username"],
      password: ["required", "password"],
    },

    submitUrl: config.apiBaseUrl + "/users/login/",

    async onSuccess(response) {
      logger.success("Login successful", response);

      // Check if response has standardized format {code, data, msg}
      if (response.code !== 200) {
        // Handle error response with code: 500
        throw new Error(response.msg || "Login failed");
      }

      // Show success notification
      const Alpine = window.Alpine;
      if (Alpine?.store("notification")) {
        Alpine.store("notification").show(response.msg || "Login successful!", "success", 1500);
      }

      // Redirect after delay
      setTimeout(() => {
        window.location.href = "/myapp/index/";
      }, 1500);
    }
  });
}

/**
 * Register Form Component (Basic)
 * Simple registration component using createFormComponent
 * For enhanced version, use register-form.js
 *
 * @returns {Object} Alpine.js component
 */
export function registerFormBasic() {
  return createFormComponent({
    initialData: {
      username: "",
      email: "",
      password: "",
      confirmPassword: "",
    },

    validationRules: {
      username: ["required", "username"],
      email: ["required", "email"],
      password: ["required", "password"],
      confirmPassword: ["required"],
    },

    submitUrl: "/myapp/register/",

    // Override validateForm to add password confirmation check
    validateForm() {
      const baseValid = this.__proto__.validateForm.call(this);

      if (this.formData.password !== this.formData.confirmPassword) {
        this.errors.confirmPassword = "Passwords do not match";
        return false;
      }

      return baseValid;
    },

    async onSuccess(response) {
      logger.success("Registration successful", response);

      const Alpine = window.Alpine;
      if (Alpine?.store("notification")) {
        Alpine.store("notification").show(
          "Registration successful!",
          "success",
          1500
        );
      }

      setTimeout(() => {
        window.location.href = response.redirect_url || "";  // 这里跳到根
      }, 1500);
    },
  });
}

/**
 * Input Field Component
 * Reusable input field with validation
 *
 * @param {string} name - Field name
 * @param {string} label - Field label
 * @param {string} type - Input type
 * @returns {Object} Alpine.js component
 */
export function inputField(name, label, type = "text") {
  return {
    name,
    label,
    type,
    focused: false,

    get hasError() {
      return !!this.$parent?.errors?.[name];
    },

    get errorMessage() {
      return this.$parent?.errors?.[name] || "";
    },

    handleBlur() {
      this.focused = false;
      if (this.$parent?.validateField) {
        this.$parent.validateField(name);
      }
    },

    handleFocus() {
      this.focused = true;
      if (this.$parent?.clearError) {
        this.$parent.clearError(name);
      }
    },
  };
}
