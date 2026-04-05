/**
 * @file Logging Utility
 * @description Centralized logging with different levels and formatting
 * @module utils/logger
 */

/**
 * Log levels
 * @enum {string}
 */
const LogLevel = {
  DEBUG: 'debug',
  INFO: 'info',
  SUCCESS: 'success',
  WARN: 'warn',
  ERROR: 'error'
};

/**
 * Logger class for application-wide logging
 * @class
 */
class Logger {
  /**
   * Create a logger instance
   * @param {boolean} enabled - Whether logging is enabled
   */
  constructor(enabled = true) {
    this.enabled = enabled;
    this.history = [];
  }
  
  /**
   * Log debug message
   * @param {...any} args - Arguments to log
   * @returns {void}
   */
  debug(...args) {
    this._log(LogLevel.DEBUG, '🔍', args);
  }
  
  /**
   * Log info message
   * @param {...any} args - Arguments to log
   * @returns {void}
   */
  info(...args) {
    this._log(LogLevel.INFO, 'ℹ️', args);
  }
  
  /**
   * Log success message
   * @param {...any} args - Arguments to log
   * @returns {void}
   */
  success(...args) {
    this._log(LogLevel.SUCCESS, '✅', args);
  }
  
  /**
   * Log warning message
   * @param {...any} args - Arguments to log
   * @returns {void}
   */
  warn(...args) {
    this._log(LogLevel.WARN, '⚠️', args);
  }
  
  /**
   * Log error message
   * @param {...any} args - Arguments to log
   * @returns {void}
   */
  error(...args) {
    this._log(LogLevel.ERROR, '❌', args);
  }
  
  /**
   * Internal log method
   * @private
   * @param {string} level - Log level
   * @param {string} emoji - Emoji prefix
   * @param {Array} args - Arguments to log
   * @returns {void}
   */
  _log(level, emoji, args) {
    if (!this.enabled) return;
    
    const timestamp = new Date().toISOString();
    const message = `${emoji} [${timestamp}]`;
    
    // Store in history
    this.history.push({ level, timestamp, args });
    
    // Keep only last 100 entries
    if (this.history.length > 100) {
      this.history.shift();
    }
    
    // Console output
    switch (level) {
      case LogLevel.DEBUG:
        console.debug(message, ...args);
        break;
      case LogLevel.INFO:
      case LogLevel.SUCCESS:
        console.log(message, ...args);
        break;
      case LogLevel.WARN:
        console.warn(message, ...args);
        break;
      case LogLevel.ERROR:
        console.error(message, ...args);
        break;
    }
  }
  
  /**
   * Get log history
   * @returns {Array} Log history
   */
  getHistory() {
    return this.history;
  }
  
  /**
   * Clear log history
   * @returns {void}
   */
  clearHistory() {
    this.history = [];
  }
}

// Export singleton instance
export const logger = new Logger(true);
