/**
 * @file Event Bus
 * @description Simple event bus for decoupled component communication
 * @module utils/event-bus
 */

/**
 * Event handler function type
 * @callback EventHandler
 * @param {any} data - Event data
 * @returns {void}
 */

/**
 * EventBus class for pub/sub pattern
 * @class
 */
class EventBus {
  /**
   * Create an event bus
   */
  constructor() {
    /** @type {Map<string, Set<EventHandler>>} */
    this.events = new Map();
  }
  
  /**
   * Subscribe to an event
   * @param {string} eventName - Event name
   * @param {EventHandler} handler - Event handler function
   * @returns {Function} Unsubscribe function
   */
  on(eventName, handler) {
    if (!this.events.has(eventName)) {
      this.events.set(eventName, new Set());
    }
    
    this.events.get(eventName).add(handler);
    
    // Return unsubscribe function
    return () => this.off(eventName, handler);
  }
  
  /**
   * Unsubscribe from an event
   * @param {string} eventName - Event name
   * @param {EventHandler} handler - Event handler function
   * @returns {void}
   */
  off(eventName, handler) {
    if (this.events.has(eventName)) {
      this.events.get(eventName).delete(handler);
    }
  }
  
  /**
   * Emit an event
   * @param {string} eventName - Event name
   * @param {any} data - Event data
   * @returns {void}
   */
  emit(eventName, data) {
    if (this.events.has(eventName)) {
      this.events.get(eventName).forEach(handler => {
        try {
          handler(data);
        } catch (error) {
          console.error(`Error in event handler for "${eventName}":`, error);
        }
      });
    }
  }
  
  /**
   * Subscribe to event once
   * @param {string} eventName - Event name
   * @param {EventHandler} handler - Event handler function
   * @returns {Function} Unsubscribe function
   */
  once(eventName, handler) {
    const onceHandler = (data) => {
      handler(data);
      this.off(eventName, onceHandler);
    };
    
    return this.on(eventName, onceHandler);
  }
  
  /**
   * Clear all event listeners
   * @returns {void}
   */
  clear() {
    this.events.clear();
  }
  
  /**
   * Get event listener count
   * @param {string} eventName - Event name
   * @returns {number} Listener count
   */
  listenerCount(eventName) {
    return this.events.has(eventName) ? this.events.get(eventName).size : 0;
  }
}

// Export singleton instance
export const eventBus = new EventBus();
