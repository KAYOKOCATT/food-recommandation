/**
 * HTTP 请求工具模块
 *
 * 封装原生 fetch API，提供统一的请求接口和错误处理
 *
 * @module utils/http
 * @author SC Food Recommendation Team
 * @created 2026-04-05
 */

/**
 * 获取 CSRF Token
 * Django CSRF 保护机制要求在 POST 请求中包含 CSRF token
 *
 * @returns {string|null} CSRF token 值
 */
function getCsrfToken() {
  const tokenElement = document.querySelector("[name=csrfmiddlewaretoken]");
  if (tokenElement) {
    return tokenElement.value;
  }

  // 从 cookie 中获取（如果使用 cookie-based CSRF）
  const cookieMatch = document.cookie.match(/csrftoken=([^;]+)/);
  return cookieMatch ? cookieMatch[1] : null;
}

/**
 * 发送 HTTP 请求
 *
 * @param {string} url - 请求 URL
 * @param {Object} options - 请求选项
 * @param {string} options.method - HTTP 方法 (GET, POST, PUT, DELETE, etc.)
 * @param {Object} options.headers - 自定义请求头
 * @param {any} options.body - 请求体数据
 * @param {boolean} options.json - 是否自动处理 JSON (默认: true)
 * @returns {Promise<any>} 响应数据
 *
 * @throws {Error} 网络错误或 HTTP 错误
 *
 * @example
 * // GET 请求
 * const data = await request('/api/users');
 *
 * // POST 请求
 * const result = await request('/api/login', {
 *     method: 'POST',
 *     body: { username: 'test', password: '123456' }
 * });
 */
export async function request(url, options = {}) {
  const { method = "GET", headers = {}, body = null, json = true } = options;

  // 构建请求配置
  const config = {
    method: method.toUpperCase(),
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    credentials: "same-origin", // 包含 cookie
  };

  // 添加 CSRF token（POST/PUT/DELETE 请求）
  if (["POST", "PUT", "PATCH", "DELETE"].includes(config.method)) {
    const csrfToken = getCsrfToken();
    if (csrfToken) {
      config.headers["X-CSRFToken"] = csrfToken;
    }
  }

  // 处理请求体
  if (body) {
    if (body instanceof FormData) {
      // FormData 不需要设置 Content-Type
      delete config.headers["Content-Type"];
      config.body = body;
    } else if (typeof body === "object") {
      config.body = JSON.stringify(body);
    } else {
      config.body = body;
    }
  }

  try {
    const response = await fetch(url, config);

    // HTTP 错误处理
    if (!response.ok) {
      const error = new Error(
        `HTTP ${response.status}: ${response.statusText}`
      );
      error.status = response.status;
      error.response = response;

      // 尝试解析错误响应体
      try {
        error.data = await response.json();
      } catch {
        error.data = await response.text();
      }

      throw error;
    }

    // 解析响应
    if (json) {
      const data = await response.json();

      // Check for standardized API format: {code, data, msg}
      // If code exists and is not 200, treat as error even if HTTP status is 200
      if (data.code !== undefined && data.code !== 200) {
        const error = new Error(data.msg || "Request failed");
        error.status = data.code;
        error.data = data;
        throw error;
      }

      return data;
    }

    return await response.text();
  } catch (error) {
    console.error("HTTP 请求失败:", error);
    throw error;
  }
}

/**
 * GET 请求快捷方法
 *
 * @param {string} url - 请求 URL
 * @param {Object} options - 额外选项
 * @returns {Promise<any>} 响应数据
 */
export function get(url, options = {}) {
  return request(url, { ...options, method: "GET" });
}

/**
 * POST 请求快捷方法
 *
 * @param {string} url - 请求 URL
 * @param {any} body - 请求体数据
 * @param {Object} options - 额外选项
 * @returns {Promise<any>} 响应数据
 */
export function post(url, body, options = {}) {
  return request(url, { ...options, method: "POST", body });
}

/**
 * PUT 请求快捷方法
 *
 * @param {string} url - 请求 URL
 * @param {any} body - 请求体数据
 * @param {Object} options - 额外选项
 * @returns {Promise<any>} 响应数据
 */
export function put(url, body, options = {}) {
  return request(url, { ...options, method: "PUT", body });
}

/**
 * DELETE 请求快捷方法
 *
 * @param {string} url - 请求 URL
 * @param {Object} options - 额外选项
 * @returns {Promise<any>} 响应数据
 */
export function del(url, options = {}) {
  return request(url, { ...options, method: "DELETE" });
}

/**
 * 提交表单数据（使用 FormData）
 *
 * @param {string} url - 请求 URL
 * @param {HTMLFormElement|FormData} formOrData - 表单元素或 FormData 对象
 * @returns {Promise<any>} 响应数据
 *
 * @example
 * const form = document.querySelector('#myForm');
 * const result = await submitForm('/api/upload', form);
 */
export async function submitForm(url, formOrData) {
  let formData;

  if (formOrData instanceof FormData) {
    formData = formOrData;
  } else if (formOrData instanceof HTMLFormElement) {
    formData = new FormData(formOrData);
  } else {
    throw new Error("参数必须是 HTMLFormElement 或 FormData 实例");
  }

  return request(url, {
    method: "POST",
    body: formData,
  });
}
