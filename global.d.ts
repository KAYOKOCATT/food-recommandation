// global.d.ts
import type { Alpine } from 'alpinejs';

// 导出 htmx 的类型（如果需要其他地方使用）
export type { 
  HttpVerb, 
  HtmxSwapStyle, 
  HtmxRequestConfig, 
  HtmxResponseInfo,
  HtmxExtension 
} from 'htmx.org';

declare global {
  interface Window {
    Alpine: Alpine;
  }
  
  // 全局变量版本（如果直接用 htmx.xxx 而不写 window.）
  var Alpine: Alpine;
  var htmx: typeof import('htmx.org').default;
}

export {};