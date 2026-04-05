/**
 * 表单验证工具模块
 * 
 * 提供常用的表单字段验证函数，遵循中国本地化规则
 * 
 * @module utils/formValidation
 * @author SC Food Recommendation Team
 * @created 2026-04-05
 */

/**
 * 验证用户名格式
 * 规则：3-20个字符，支持字母、数字、下划线、中文
 * 
 * @param {string} username - 待验证的用户名
 * @returns {boolean} 验证结果
 * 
 * @example
 * validateUsername('张三123'); // true
 * validateUsername('ab'); // false (太短)
 */
export function validateUsername(username) {
    if (!username || typeof username !== 'string') {
        return false;
    }
    
    const trimmed = username.trim();
    const minLength = 3;
    const maxLength = 20;
    
    // 长度检查
    if (trimmed.length < minLength || trimmed.length > maxLength) {
        return false;
    }
    
    // 允许：字母、数字、下划线、中文
    const usernameRegex = /^[\w\u4e00-\u9fa5]+$/;
    return usernameRegex.test(trimmed);
}

/**
 * 验证密码强度
 * 规则：至少6个字符
 * 
 * @param {string} password - 待验证的密码
 * @returns {boolean} 验证结果
 * 
 * @example
 * validatePassword('123456'); // true
 * validatePassword('12345'); // false
 */
export function validatePassword(password) {
    if (!password || typeof password !== 'string') {
        return false;
    }
    
    const minLength = 6;
    return password.length >= minLength;
}

/**
 * 验证中国大陆手机号
 * 规则：1开头，第二位为3-9，共11位数字
 * 
 * @param {string} phone - 待验证的手机号
 * @returns {boolean} 验证结果
 * 
 * @example
 * validatePhone('13812345678'); // true
 * validatePhone('12345678901'); // false
 */
export function validatePhone(phone) {
    if (!phone || typeof phone !== 'string') {
        return false;
    }
    
    const phoneRegex = /^1[3-9]\d{9}$/;
    return phoneRegex.test(phone.trim());
}

/**
 * 验证电子邮箱格式
 * 规则：标准 RFC 5322 简化版
 * 
 * @param {string} email - 待验证的邮箱
 * @returns {boolean} 验证结果
 * 
 * @example
 * validateEmail('user@example.com'); // true
 * validateEmail('invalid-email'); // false
 */
export function validateEmail(email) {
    if (!email || typeof email !== 'string') {
        return false;
    }
    
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email.trim());
}

/**
 * 验证表单字段是否为空
 * 
 * @param {string} value - 待验证的值
 * @returns {boolean} 如果为空返回 false，否则返回 true
 * 
 * @example
 * validateRequired('hello'); // true
 * validateRequired('   '); // false
 * validateRequired(''); // false
 */
export function validateRequired(value) {
    if (value === null || value === undefined) {
        return false;
    }
    
    if (typeof value === 'string') {
        return value.trim().length > 0;
    }
    
    return true;
}

/**
 * 获取字段验证错误消息
 * 
 * @param {string} fieldName - 字段名称
 * @param {string} validationType - 验证类型
 * @returns {string} 错误消息
 */
export function getValidationMessage(fieldName, validationType) {
    const messages = {
        required: `${fieldName}不能为空`,
        username: '用户名格式不正确（3-20个字符，支持字母、数字、下划线、中文）',
        password: '密码至少需要6个字符',
        phone: '手机号格式不正确',
        email: '电子邮箱格式不正确'
    };
    
    return messages[validationType] || '字段验证失败';
}

/**
 * 批量验证表单数据
 * 
 * @param {Object} formData - 表单数据对象
 * @param {Object} rules - 验证规则对象
 * @returns {Object} { valid: boolean, errors: Object }
 * 
 * @example
 * const result = validateForm(
 *     { username: 'test', email: 'test@example.com' },
 *     { 
 *         username: ['required', 'username'], 
 *         email: ['required', 'email'] 
 *     }
 * );
 * // result: { valid: true, errors: {} }
 */
export function validateForm(formData, rules) {
    const errors = {};
    let valid = true;
    
    const validators = {
        required: validateRequired,
        username: validateUsername,
        password: validatePassword,
        phone: validatePhone,
        email: validateEmail
    };
    
    for (const [field, fieldRules] of Object.entries(rules)) {
        const value = formData[field];
        
        for (const rule of fieldRules) {
            const validator = validators[rule];
            
            if (validator && !validator(value)) {
                errors[field] = getValidationMessage(field, rule);
                valid = false;
                break; // 只显示第一个错误
            }
        }
    }
    
    return { valid, errors };
}
