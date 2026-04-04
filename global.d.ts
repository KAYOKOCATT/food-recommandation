// global.d.ts
import { Alpine } from 'alpinejs';
import type htmx from 'htmx.org';  // 仅导入类型，不导入值

declare global {
  interface Window {
    Alpine: Alpine;
    htmx: typeof import('htmx.org').default;  // 另一种获取 default export 类型的方式
  }
  
  var Alpine: Alpine;
  var htmx: typeof import('htmx.org').default;
}

export {};