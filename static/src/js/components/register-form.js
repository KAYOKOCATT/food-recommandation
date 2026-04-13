/**
 * @file Register Form Component
 * @description Enhanced registration form with comprehensive validation
 * @module components/register-form
 */

import { config } from "../main.js";
import {
  validateUsername,
  validatePassword,
  validatePhone,
  validateEmail,
  validateRequired,
} from "../utils/formValidation.js";
import { post } from "../utils/http.js";
import { logger } from "../utils/logger.js";

// NOTE: Don't cache Alpine at module load time - it may not be loaded yet
// Access window.Alpine at runtime instead

/**
 * Registration Form Component
 *
 * Modern Vue-style component with:
 * - Reactive data binding
 * - Field-level validation
 * - Password confirmation
 * - Async form submission
 * - Global state integration
 *
 * @returns {Object} Alpine.js component instance
 */
export function registerForm() {
  return {
    // ==================== Reactive State ====================

    /**
     * Form data model
     * @type {Object}
     */
    formData: {
      username: "",
      password: "",
      confirmPassword: "",
      phone: "",
      email: "",
      agreeToTerms: false,
    },

    /**
     * Field-level error messages
     * @type {Object.<string, string>}
     */
    errors: {
      username: "",
      password: "",
      confirmPassword: "",
      phone: "",
      email: "",
    },

    /**
     * Submission state flag
     * @type {boolean}
     */
    isSubmitting: false,

    /**
     * Field touched state (for progressive validation UX)
     * @type {Object.<string, boolean>}
     */
    touched: {
      username: false,
      password: false,
      confirmPassword: false,
      phone: false,
      email: false,
    },

    // ==================== Lifecycle Hooks ====================

    /**
     * Component initialization
     */
    init() {
      logger.debug("Register form component initialized");

      // Setup real-time validation for password confirmation
      this.$watch("formData.password", () => {
        if (this.touched.confirmPassword && this.formData.confirmPassword) {
          this.validateField("confirmPassword");
        }
      });
    },

    // ==================== Computed Properties ====================

    /**
     * Check if form is valid
     * @returns {boolean}
     */
    get isFormValid() {
      return this.validateForm(false);
    },

    /**
     * Check if submit button should be disabled
     * @returns {boolean}
     */
    get isSubmitDisabled() {
      return this.isSubmitting || !this.formData.agreeToTerms;
    },

    // ==================== Validation Methods ====================

    /**
     * Validate single field with specific rules
     *
     * @param {string} field - Field name
     * @returns {boolean} Validation result
     */
    validateField(field) {
      const value = this.formData[field];

      // Mark field as touched
      this.touched[field] = true;

      // Clear previous error
      this.errors[field] = "";

      // Required validation
      if (!validateRequired(value)) {
        this.errors[field] = this.getFieldLabel(field) + " cannot be empty";
        return false;
      }

      // Field-specific validation
      const validationMap = {
        username: {
          validator: validateUsername,
          message:
            "Username format is incorrect (3-20 characters, supports Chinese, letters, numbers, underscore)",
        },
        password: {
          validator: validatePassword,
          message: "Password must be at least 6 characters",
        },
        confirmPassword: {
          validator: (val) => val === this.formData.password,
          message: "Passwords do not match",
        },
        phone: {
          validator: validatePhone,
          message: "Please enter a valid Chinese mainland mobile number",
        },
        email: {
          validator: validateEmail,
          message: "Please enter a valid email address",
        },
      };

      const validation = validationMap[field];
      if (validation && !validation.validator(value)) {
        this.errors[field] = validation.message;
        return false;
      }

      // If password changed and confirm password exists, revalidate confirm password
      if (
        field === "password" &&
        this.formData.confirmPassword &&
        this.touched.confirmPassword
      ) {
        setTimeout(() => this.validateField("confirmPassword"), 0);
      }

      return true;
    },

    /**
     * Validate entire form
     *
     * @param {boolean} showErrors - Whether to show error messages
     * @returns {boolean} Overall validation result
     */
    validateForm(showErrors = true) {
      const fields = [
        "username",
        "password",
        "confirmPassword",
        "phone",
        "email",
      ];
      let isValid = true;

      for (const field of fields) {
        if (showErrors) {
          if (!this.validateField(field)) {
            isValid = false;
          }
        } else {
          // Silent validation
          const value = this.formData[field];
          if (!validateRequired(value)) {
            isValid = false;
            continue;
          }

          // Quick validation without setting errors
          if (field === "username" && !validateUsername(value)) isValid = false;
          if (field === "password" && !validatePassword(value)) isValid = false;
          if (field === "confirmPassword" && value !== this.formData.password)
            isValid = false;
          if (field === "phone" && !validatePhone(value)) isValid = false;
          if (field === "email" && !validateEmail(value)) isValid = false;
        }
      }

      return isValid;
    },

    /**
     * Clear error for specific field
     *
     * @param {string} field - Field name
     */
    clearError(field) {
      this.errors[field] = "";
    },

    /**
     * Get field label in English
     *
     * @param {string} field - Field name
     * @returns {string} Field label
     */
    getFieldLabel(field) {
      const labels = {
        username: "Username",
        password: "Password",
        confirmPassword: "Confirm Password",
        phone: "Phone Number",
        email: "Email",
      };
      return labels[field] || field;
    },

    // ==================== Business Logic ====================

    /**
     * Handle form submission
     *
     * Flow:
     * 1. Validate all fields
     * 2. Check user agreement
     * 3. Send async request
     * 4. Handle response (success/error)
     * 5. Update global notification
     * 6. Navigate to login page
     *
     * @param {Event} event - Submit event
     */
    async handleSubmit(event) {
      event?.preventDefault();

      logger.info("Register form submission started");

      // Validate form
      if (!this.validateForm(true)) {
        logger.warn("Form validation failed", this.errors);
        this.showNotification("Please correct the errors in the form", "error");
        window.alert("请先修正表单中的错误");
        return;
      }

      // Check user agreement
      if (!this.formData.agreeToTerms) {
        this.showNotification(
          "Please agree to the Terms of Service and Privacy Policy",
          "warning"
        );
        window.alert("请先同意服务条款和隐私政策");
        return;
      }

      this.isSubmitting = true;

      try {
        // Send registration request
        const response = await post(config.apiBaseUrl + "/users/register/", {
          username: this.formData.username,
          password: this.formData.password,
          phone: this.formData.phone,
          email: this.formData.email,
        });

        logger.success("Registration successful", response);
        window.alert(response.msg || "注册成功");

        // Show success notification
        this.showNotification(
          "Registration successful! Redirecting to login page...",
          "success",
          2000
        );

        // Redirect to login page
        setTimeout(() => {
          window.location.href = "/"; // 这里跳到根
        }, 2000);
      } catch (error) {
        this.isSubmitting = false;

        logger.error("Registration failed", error);

        // Handle server errors
        if (error.data && (error.data.error || error.data.msg)) {
          const errorMsg = error.data.error || error.data.msg;
          window.alert(errorMsg);

          // Show error notification
          this.showNotification(errorMsg, "error");

          // Map error to specific field
          this.mapServerError(errorMsg);
        } else {
          // Network or unknown error
          window.alert("网络错误，请稍后重试");
          this.showNotification(
            "Network error, please try again later",
            "error"
          );
        }
      }
    },

    /**
     * Map server error message to form field
     *
     * @param {string} errorMsg - Error message from server
     */
    mapServerError(errorMsg) {
      const errorMap = {
        username: ["Username", "username", "user name"],
        phone: ["Phone", "phone", "mobile"],
        email: ["Email", "email", "e-mail"],
      };

      for (const [field, keywords] of Object.entries(errorMap)) {
        if (keywords.some((keyword) => errorMsg.includes(keyword))) {
          this.errors[field] = errorMsg;
          break;
        }
      }
    },

    /**
     * Show notification using global store
     *
     * @param {string} message - Notification message
     * @param {string} type - Notification type
     * @param {number} duration - Display duration
     */
    showNotification(message, type = "info", duration = 5000) {
      const Alpine = window.Alpine;
      if (Alpine?.store("notification")) {
        Alpine.store("notification").show(message, type, duration);
      } else {
        logger.warn("Notification store not available");
      }
    },

    /**
     * Reset form to initial state
     */
    resetForm() {
      this.formData = {
        username: "",
        password: "",
        confirmPassword: "",
        phone: "",
        email: "",
        agreeToTerms: false,
      };

      this.errors = {
        username: "",
        password: "",
        confirmPassword: "",
        phone: "",
        email: "",
      };

      this.touched = {
        username: false,
        password: false,
        confirmPassword: false,
        phone: false,
        email: false,
      };

      this.isSubmitting = false;

      logger.debug("Form reset completed");
    },
  };
}
