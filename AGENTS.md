# Repository Guidelines

## Project Structure & Module Organization

- `apps/` contains Django apps. `apps/foods` holds dish business logic, `apps/users` handles auth/profile flows, and `apps/recommendations` contains recommendation services, chart APIs, and tests.
- `config/` contains Django settings, URL routing, WSGI/ASGI entrypoints.
- `templates/` stores Django templates; `templates/auth/` is the main user-facing UI.
- `static/` contains CSS, JS, and image assets. Keep new frontend code close to the page that uses it.
- `data/` stores offline recommendation artifacts such as `data/recommendations/food_itemcf.json`.
- `get_data/` contains scraping and import scripts. `notebooks/` is for exploratory work, not production runtime logic.

## Build, Test, and Development Commands

- `.\.venv\Scripts\python.exe manage.py runserver` starts the Django dev server.
- `.\.venv\Scripts\python.exe manage.py check` runs Django system checks.
- `.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run` verifies model changes are migration-safe.
- `.\.venv\Scripts\python.exe -m mypy apps config` runs type checks.
- `.\.venv\Scripts\python.exe -m pylint apps config` runs lint checks.
- `.\.venv\Scripts\python.exe manage.py test apps.recommendations.tests` runs the current Python test suite.

## Coding Style & Naming Conventions

- Use 4-space indentation in Python and keep lines near the `pylint` limit of 100 chars.
- Prefer explicit, small service functions over view-heavy logic.
- Use `snake_case` for Python functions, variables, and module names; Django models remain singular class names like `Foods`, `User`, `Collect`.
- Keep recommendation logic in services/modules, not in templates or notebooks.
- Static checks are configured in `pyproject.toml`; do not introduce ad hoc local tool settings.

## Testing Guidelines

- Add tests under `apps/<app>/tests/` with names like `test_<feature>.py`.
- Favor deterministic tests for offline recommendation logic with small fixed matrices or sample JSON.
- When changing recommendation file loading, cover missing file, malformed JSON, and empty-result cases.

## Commit & Pull Request Guidelines

- Recent history uses short Chinese messages focused on behavior changes, often starting with `fix:`. Keep commits concise and action-oriented, for example: `fix: 修复详情页相似菜品空列表`.
- PRs should include: purpose, affected app(s), key commands run, migration impact, and screenshots for template/UI changes.

## Security & Configuration Tips

- Keep secrets in environment variables such as `DJANGO_SECRET_KEY`, `MYSQL_*`; never commit real credentials.
- Treat generated collect/recommendation data as demo or offline artifacts unless explicitly documented as real evaluation data.

---

# Frontend Architecture Guidelines

## 双轨前端架构

本项目采用**传统与现代共存**的双轨架构：

### 传统架构（jQuery + Bootstrap 4）
- 基模板：`templates/layout.html`
- 用途：大部分页面沿用既有 UI 组件
- 资源：`/static/css/`, `/static/js/` 下的传统资源

### 现代架构（HTMX + Alpine.js + ES Modules）
- 认证页面基模板：`templates/base_auth.html`（无侧边栏）
- 内部页面基模板：`templates/base_modern.html`（继承 layout.html）
- 图表页面基模板：`templates/base_chart.html`（ECharts 支持）

## 模板继承体系

```
base_auth.html          base_modern.html          base_chart.html
    ↓                        ↓                         ↓
无侧边栏页面         layout.html (传统)           layout.html
                              ↓
                       带侧边栏现代页面
```

**选择指南**：
- 登录/注册 → `base_auth.html`
- 内部数据展示页面 → `base_modern.html`
- ECharts 图表页面 → `base_chart.html`

## Alpine.js 加载策略（关键）

**正确加载顺序**（必须在 `<head>` 中按此顺序）：

```html
<!-- 1. 内联 Alpine 组件定义（如 toastContainer）-->
<script>
  function toastContainer() { return { ... }; }
</script>

<!-- 2. main.js 作为 module - 监听 'alpine:init' -->
<script type="module" src="{% static 'src/js/main.js' %}"></script>

<!-- 3. Alpine.js CDN - 触发 'alpine:init' -->
<script defer src="{% static '/src/lib/alpine.js' %}"></script>
```

**关键原则**：
- `main.js` 必须先执行以注册 `alpine:init` 事件监听
- Alpine 后加载，就绪时触发 `alpine:init`
- 内联组件（如 `toastContainer`）必须在 Alpine 之前定义

## HTMX 使用规范

**CSRF 保护**：
```html
<body hx-headers='{"x-csrftoken": "{{ csrf_token }}"}'>
```

**路径格式**：使用带前导斜杠的路径
```html
<script defer src="{% static '/src/lib/htmx.js' %}"></script>
```

**与 Django 集成**：
- 已配置 `django_htmx` middleware
- API 返回格式：`{code: 200, data: {}, msg: ""}`

## 静态文件组织

```
static/
├── css/                    # Bootstrap 4 等传统样式
├── js/                     # jQuery 等传统脚本
└── src/
    ├── lib/                # HTMX, Alpine.js CDN 文件
    │   ├── htmx.js
    │   ├── alpine.js
    │   └── ...
    └── js/                 # ES Module 源码
        ├── main.js         # 应用入口
        ├── components/     # Alpine 组件
        └── utils/          # 工具函数
```

## 组件开发规范

**Alpine 组件注册**（main.js）：
```javascript
document.addEventListener('alpine:init', () => {
  Alpine.data('componentName', componentFunction);
});
```

**Toast 通知使用**：
```javascript
// 显示成功消息
document.dispatchEvent(new CustomEvent('showToast', {
  detail: { message: '操作成功', type: 'success' }
}));

// 类型: info, success, error
```

## 废弃项

- ❌ 不再使用 django-compressor
- ❌ 不再使用 SCSS（已删除 `/static/src/scss/`）
- ❌ 不再使用 `{% load compress %}`
