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
          error.data?.error || error.data?.msg || error.message || "Submission failed";
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
  const component = createFormComponent({
    initialData: {
      username: "",
      password: "",
      remember: false,
      selectedYelpUser: "",
      login_mode: "local",
    },

    submitUrl: config.apiBaseUrl + "/users/login/",

    async onSuccess(response) {
      logger.success("Login successful", response);
      showBrowserAlert(response.msg || "登录成功");
      redirectWithNotification(response, "登录成功");
    },

    async onError(error) {
      const message =
        error.data?.error ||
        error.data?.msg ||
        error.message ||
        "登录失败，请稍后重试";
      showBrowserAlert(message);
      this.handleError(error);
    }
  });

  return {
    ...component,
    isYelpPickerOpen: false,

    get isDemoMode() {
      return this.formData.login_mode === "yelp_demo";
    },

    get loginModeLabel() {
      if (this.formData.login_mode === "yelp_demo") {
        return "Yelp 演示身份";
      }
      return "本地账号";
    },

    toggleYelpPicker() {
      this.isYelpPickerOpen = !this.isYelpPickerOpen;
    },

    closeYelpPicker() {
      this.isYelpPickerOpen = false;
    },

    validateField(field) {
      this.errors[field] = "";

      if (field === "selectedYelpUser" && this.formData.login_mode === "yelp_demo") {
        if (!this.formData.selectedYelpUser) {
          this.errors.selectedYelpUser = "请选择 Yelp 演示账号";
          return false;
        }
        return true;
      }

      if (this.formData.login_mode === "local") {
        return component.validateField.call(this, field);
      }

      if (field === "username") {
        if (!this.formData.username?.trim()) {
          this.errors.username = "用户名不能为空";
          return false;
        }
      }

      return true;
    },

    validateForm() {
      this.errors = {};

      if (this.formData.login_mode === "yelp_demo") {
        if (!this.formData.selectedYelpUser) {
          this.errors.selectedYelpUser = "请选择 Yelp 演示账号";
        }
        if (!this.formData.username?.trim()) {
          this.errors.username = "用户名不能为空";
        }
        return Object.keys(this.errors).length === 0;
      }

      return component.validateForm.call(this);
    },

    selectYelpUser() {
      const selectedOption = this.$refs.yelpUserSelect?.selectedOptions?.[0];
      const selectedLabel = selectedOption?.dataset?.username || selectedOption?.textContent?.trim();

      this.formData.login_mode = this.formData.selectedYelpUser ? "yelp_demo" : "local";
      this.formData.username = this.formData.selectedYelpUser ? (selectedLabel || "") : "";
      this.formData.password = "";
      this.closeYelpPicker();
      this.clearError("selectedYelpUser");
      this.clearError("username");
      this.clearError("password");
    },

    useLocalLogin() {
      this.resetForm();
      this.formData.login_mode = "local";
      this.formData.selectedYelpUser = "";
      this.closeYelpPicker();
    },

    passwordPlaceholder() {
      if (this.formData.login_mode === "yelp_demo") {
        return "已选择 Yelp 演示身份，无需输入密码";
      }
      return "密码";
    },

    showNotification(message, type = "info", duration = 3000) {
      const Alpine = window.Alpine;
      if (Alpine?.store("notification")) {
        Alpine.store("notification").show(message, type, duration);
      }
    },
  };
}

function redirectWithNotification(response, fallbackMessage) {
  const Alpine = window.Alpine;
  if (Alpine?.store("notification")) {
    Alpine.store("notification").show(
      response.msg || fallbackMessage,
      "success",
      1200
    );
  }

  setTimeout(() => {
    window.location.href = response.data?.redirect || "/";
  }, 1200);
}

function showBrowserAlert(message) {
  window.alert(message);
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

    submitUrl: config.apiBaseUrl + "/users/register/",

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
