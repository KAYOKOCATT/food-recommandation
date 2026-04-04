# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

餐饮个性化推荐系统 - A Django-based food recommendation system using collaborative filtering algorithms. The project combines a modern frontend stack (HTMX + Alpine.js + SCSS + ES Modules) with Django's server-side rendering.

## Development Commands

```bash
# Start Django development server
python manage.py runserver
# or
npm run dev

# Collect static files and compile SCSS (production)
python manage.py collectstatic --noinput
python manage.py compress
# or
npm run build

# Database migrations
python manage.py makemigrations
python manage.py migrate

# Type checking (requires mypy/django-stubs setup)
mypy apps/

# Template linting
djlint templates/
```

## Architecture Overview

### Backend (Django)

- **Django 5.2** with custom User model in `apps/users/models.py`
- **MySQL 8.0** database (configured in `config/settings.py`)
- **App structure**: All apps under `apps/` directory (users, foods, ratings, recommendations)
- **URL routing**: `config/urls.py` includes app-specific URL configs
- **Static files**: Served via WhiteNoise with compression

### Frontend Stack

**Tech Stack Combination:**
- **HTMX 2.0.8** (`static/src/lib/htmx.esm.js`) - Server-driven interactivity, AJAX requests
- **Alpine.js 3.14.1** (`static/src/lib/alpine.esm.js`) - Reactive components, state management
- **SCSS** - Modular styles following 7-1 architecture pattern
- **ES Modules** - Native module system with import maps
- **JSDoc** - Type annotations for IDE type checking

**Key Files:**
- `static/src/js/main.js` - Entry point, initializes HTMX/Alpine, registers components
- `static/src/scss/main.scss` - SCSS entry point with imports
- `templates/base.html` - Base template with HTMX script and compress tags
- `global.d.ts` - TypeScript declarations for Alpine/HTMX

**Component Pattern:**
Alpine.js components are defined in `static/src/js/components/` and registered in `main.js`:
```javascript
Alpine.data("componentName", componentFunction);
```

Forms use a factory pattern (`createFormComponent`) with validation rules and HTTP utilities.

### Static Assets Pipeline

- **django-compressor** compiles SCSS → CSS and minifies JS
- **Development**: SCSS compiled on-the-fly via `text/x-scss` precompiler
- **Production**: Set `COMPRESS_OFFLINE = True`, run `python manage.py compress`
- **WhiteNoise** serves static files with compression and caching headers

Template usage:
```django
{% load compress %}
{% compress css %}
  <link rel="stylesheet" type="text/x-scss" href="{% static 'src/scss/main.scss' %}">
{% endcompress %}
```

## Project Structure

```
├── apps/
│   ├── users/           # User auth, User/Foods models
│   ├── foods/           # Food-related views (if separate)
│   ├── ratings/         # Rating system
│   └── recommendations/ # Recommendation algorithms
├── config/              # Django settings, URLs, WSGI/ASGI
├── static/
│   ├── src/
│   │   ├── js/          # ES modules (main.js, utils/, components/)
│   │   ├── scss/        # SCSS with 7-1 architecture
│   │   └── lib/         # Vendored ESM libraries (Alpine, HTMX)
│   └── (legacy CSS files)
├── staticfiles/         # collectstatic output (gitignored)
├── templates/           # Django templates
│   ├── base.html        # Base layout with HTMX/SCSS setup
│   ├── auth/            # Login/register templates
│   └── components/      # Reusable template components
├── docs/                # Architecture documentation
├── get_data/            # Data scraping scripts
├── requirements.txt     # Python dependencies
└── package.json         # Node deps (types only, no bundler)
```

## Key Conventions

**JavaScript:**
- ES Modules with JSDoc type annotations
- Utilities in `static/src/js/utils/`: logger.js, http.js, formValidation.js, event-bus.js, htmx-config.js
- Components export factory functions returning Alpine component objects
- HTTP requests use wrapper in `utils/http.js` with CSRF handling

**SCSS:**
- 7-1 architecture: abstracts/, base/, layout/, components/, utilities/
- Variables and mixins in `abstracts/`
- Component styles match Alpine component names where applicable

**Django:**
- Models include comprehensive docstrings with type hints (TYPE_CHECKING for Manager)
- Views use type hints: `HttpRequest` → `Union[JsonResponse, HttpResponse]`
- API responses follow format: `{'code': int, 'data': {}, 'msg': str}`
- Custom User model with automatic password hashing in `save()`

**HTMX Integration:**
- CSRF token injected via `hx-headers` on body tag
- Event handlers in `htmx-config.js` manage loading states and errors
- `django-htmx` middleware provides request.htmx detection
