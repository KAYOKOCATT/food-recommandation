  # 登录阶段与入口治理实现计划

  ## Summary

  本阶段不只补登录接口，而是把“登录入口、身份判定、菜单注入、URL 分组、相关模板归位”作为一个整体收敛掉，但范围限定在登录与登录后入口链路，不扩展到完整后台 CRUD。

  采用的方向：

  - 身份模型不做重 RBAC，只区分 local user、yelp demo user、admin demo 三类会话身份。
  - 侧边栏菜单改为服务端 Python 配置注入，模板只负责渲染。
  - URL 统一按业务域分组，清理当前根级快捷路径和硬编码跳转。
  - 顺手整理与登录阶段直接相关的模板位置，先把“活跃模板”和“历史模板”边界拉清。

  ## Public Interfaces

  ### Session 约定

  继续保留 user_id，并新增：

  - auth_role: user 或 admin
  - login_source: local、yelp_demo、admin_demo
  - is_demo_login: true/false

  ### URL 统一方案

  这次统一成按域分组：

  - GET /：登录页
  - POST /api/v1/users/login/：本地用户名密码登录
  - POST /api/v1/users/login/yelp-demo/：Yelp 演示登录
  - POST /api/v1/users/login/admin-demo/：管理员演示登录
  - POST|GET /api/v1/users/logout/：退出
  - GET /api/v1/users/home/：普通用户首页
  - GET /api/v1/users/profile/：个人中心
  - GET|POST /api/v1/users/password/：修改密码
  - GET /api/v1/admin/home/：管理员首页占位页
  - GET /api/v1/foods/list/、/detail/<id>/、/recommendations/*
  - GET /api/v1/yelp/restaurants/、/restaurants/<business_id>/
  - GET /api/v1/yelp/recommendations/：Yelp 演示用户推荐页
  - POST /api/v1/yelp/restaurants/<business_id>/review/

  不再继续新增根级 /api/v1/user_index/、/api/v1/food_list/、/api/v1/logout/ 这类快捷路由。

  ## Implementation Changes

  ### 1. 抽出轻量身份与菜单基础设施

  在 apps/users 内新增一个轻量访问控制层：

  - 统一从 session 解析当前用户与身份。
  - 统一建立三类登录 session。
  - 提供页面访问守卫和接口访问守卫。
  - 集中定义“当前身份可见菜单”。

  菜单用 Python 配置表达，不做数据库化：

  - 菜单项字段固定为：key、label、icon、url_name、children、visible_when
  - visible_when 只接受简单身份条件，不做复杂权限表达式
  - context processor 负责把过滤后的菜单列表注入模板

  这样后续新增后台页或 Yelp 推荐入口，只改 Python 配置，不再把身份判断散落到 layout.html。

  ### 2. 重构 URL 组织

  收敛 config/urls.py：

  - 根路由只保留登录页与各 app include。
  - 所有业务 URL 通过 apps.users.urls、apps.foods.urls、apps.recommendations.urls、新增的 apps.adminpanel.urls（或先挂在 users/admin 域）暴露。
  - 清理直接引用 view 的顶层 path，避免同一路径在多处定义。

  同步清理代码中的硬编码跳转和模板中的硬编码 href：

  - 全部改用 name + {% url %} 或服务端返回的标准 redirect URL
  - 前端 Alpine 登录成功后的跳转地址由后端响应决定，不在 JS 里写死 /api/v1/user_index/

  ### 3. 登录页扩展为三入口

  保留现有本地登录，新增两个演示入口：

  - Yelp 演示登录：
      - 服务端选出 source="yelp" 且有至少一条 YelpReview 的用户
      - 按评论活跃度排序，只返回前 30 个账号供页面选择
      - 登录成功跳转 yelp_recommendations
  - 管理员演示登录：
      - 使用 User 表第一条记录
      - 登录成功跳转 admin_home

  登录响应统一返回：

  - code
  - msg
  - data.user_id
  - data.redirect

  前端登录页只负责展示三入口，不承担权限逻辑。

  ### 4. 明确三类身份边界

  边界保持简单、可预测：

  - local user
      - 可访问普通首页、个人中心、改密
      - 可做中文菜品收藏/评论
      - 可提交 Yelp 站内评分评论
  - yelp demo user
      - 可访问 Yelp 列表、详情、Yelp 推荐页
      - 不可访问个人资料编辑、改密
      - 不可提交中文菜品收藏/评论
      - 不可提交 Yelp 新评论，避免污染演示账号
  - admin demo
      - 仅可访问管理员首页及后续后台入口
      - 不走普通用户个人中心与交互链路

  受保护视图统一改造：

  - 页面请求：未授权重定向到登录页；已登录但越权返回 403 页面或明确提示页
  - API 请求：返回 JSON 401/403，结构统一

  ### 5. 侧边栏与头部模板改为数据驱动

  修改 templates/layout.html：

  - 头部用户区显示当前身份标签，例如“本地用户 / Yelp 演示 / 管理员演示”
  - 侧边栏遍历 nav_menu 渲染，不再硬编码菜单项
  - 当前激活状态由当前 route name 或 request.path 匹配判断
  - 退出链接使用命名路由

  菜单分三套可见集合：

  - 普通用户菜单
  - Yelp 演示菜单
  - 管理员菜单

  不拆三份菜单模板；只保留一份渲染模板和一份 Python 菜单配置。

  ### 6. 登录相关模板归位

  这次只整理与登录阶段直接相关的模板，不做全仓模板大搬家：

  - 保留 templates/auth/ 存放本地用户页面
  - 保留 templates/recommendations/ 存放 Yelp 页面
  - 新增 templates/adminpanel/ 或 templates/admin_portal/ 存放管理员首页占位页
  - templates/legacy/ 明确视为历史模板，不参与运行时入口

  同步补一份简短文档，说明：

  - 哪些模板是运行时有效模板
  - 哪些目录是历史素材
  - 登录后入口页面各自对应哪个模板域

  - Yelp 推荐页：
      - 有结果显示推荐列表
      - 无结果时展示降级文案和返回 Yelp 餐厅列表入口
  - 管理员首页占位页：
      - 展示当前管理员身份
      - 展示后续 CRUD 模块入口占位
      - 作为后台主入口，为下一阶段后台治理做承接

  ## Test Plan

  补充 Django tests，覆盖以下场景：

  - 三种登录成功后 session 标记正确，且 redirect 正确
  - Yelp 演示登录仅允许 source="yelp" 且有评论的账号
  - 管理员演示登录在 User 为空时失败
  - 本地用户访问管理员首页被拒绝
  - Yelp 演示用户访问个人中心、改密、中文菜品收藏评论、Yelp 评分接口被拒绝
  - 管理员访问普通用户页面和交互接口被拒绝
  - 菜单注入测试：
      - 三类身份拿到的 nav_menu 不同
      - 菜单 URL 都能通过命名路由反解
  - URL 统一测试：
      - reverse() 指向新的分组路由
      - 登录成功响应中的 redirect 使用新 URL
  - Yelp 推荐页降级测试：
      - 文件缺失
      - JSON 损坏
      - 候选为空
      - 都返回 200 并展示降级文案
  - 退出后 session 清空，受保护页面重新需要登录

  ## Assumptions

  - 本阶段不实现完整 RBAC，只做三类固定身份 + 菜单过滤 + 访问边界。
  - 本阶段不实现数据库化菜单，菜单配置留在 Python 常量/函数中。
  - 只整理与登录链路直接相关的 URL 和模板；templates/legacy/ 暂不搬迁，只明确其历史性质。
  - 为降低切换风险，前端和模板中的路径全部改成命名路由，避免后续再次整理 URL 时重复修改。
  - 管理员域先做首页占位页，不在本阶段展开 CRUD 页面实现。