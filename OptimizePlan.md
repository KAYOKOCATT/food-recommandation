  # Yelp 大规模导入影响分析与优化计划

  ## Summary

  当前 import_yelp_data 的限量方式是“各文件前 N 行”，在你已经导入约 200W 用户、300W 评论后，影响不只在离线导入阶段，也已经进入运行时路径。
  已确认的高影响点里，登录首屏变慢最可疑的直接原因是：apps.users.views.login() 在 GET 时会执行 _get_yelp_demo_users()，该查询会对全量 source="yelp" 用户做 Count("yelp_reviews")
  聚合、过滤 review_count__gt=0、排序，再取前 30。面对百万级用户和评论，这会成为登录页的重查询。

  除登录页外，当前巨量导入还会影响：

  - 导入阶段内存：评论导入前会把全部 Yelp 餐厅 business_id 和全部 Yelp 用户映射一次性读入 Python 内存。
  - 导入阶段耗时：评论导入后会执行全量 refresh_aggregated_review_counts()，相当于扫全体已导入商家和评论。
  - 推荐构建：build_yelp_review_usercf 直接基于数据库全量 YelpReview 构建，评论规模越大，构建耗时和输出 JSON 体积越大。
  - 运行时推荐：get_usercf_recommendations() 每次都要先查当前用户已看过的全部 YelpReview；数据越大，活跃账号越重。
  - Yelp 列表/图表：虽然已分页或有限流，但底表和索引规模增长会抬高排序、聚合和缓存失效成本。

  ## Key Changes

  ### 1. 先把“登录首屏慢”从全量聚合改成轻量候选源

  目标：登录页不能直接对全量 Yelp 用户做实时聚合排序。

  实现方案：

  - 新增“Yelp 演示账号候选”离线/准离线来源，不再在登录 GET 请求里实时 Count(yelp_reviews)。
  - 候选源优先用以下任一轻量物化结果：
      - 推荐默认：单独表或 JSON/缓存文件，保存 user_id、review_count、最近更新时间、展示名。
      - 备选：直接用 User 表新增预计算字段 yelp_review_count 与 is_demo_candidate。
  - 登录页只读取前 30 个候选，不再临时做聚合。
  - 候选刷新时机：
      - Yelp 用户/评论导入完成后刷新一次。
      - 后续允许增量导入时，仅刷新受影响用户。
  - 登录页性能验收标准：
      - 未登录 GET / 不触发 COUNT(yelp_reviews) 聚合。
      - 页面首屏数据库查询固定为“少量简单查询”。

  ### 2. 把导入限制从“按前 N 行”改成“按业务可用样本集”

  目标：导入结果适合演示和推荐，而不是简单截断原始文件前缀。

  实现方案：

  - 新增“活跃度筛选”的导入模式，作为主线。
  - businesses：
      - 继续先筛餐厅，再按 review_count、城市覆盖、营业状态过滤，控制在目标餐厅规模。
  - users：
      - 不再独立按 user-limit 读前 N 行。
      - 改为“先确定保留评论，再只保留这些评论涉及到的用户”。
  - reviews：
      - 不再简单按 review 文件前 N 行。
      - 改为优先导入“命中目标餐厅 + 命中目标用户”的评论。
  - 推荐默认目标规模：
      - 1-5 万餐厅
      - 10-30 万用户
      - 50-150 万评论
  - 这样能保证：
      - 登录演示账号更活跃
      - Yelp 推荐覆盖更稳定
      - 数据量对本地开发仍可控

  ### 3. 重做导入数据流，避免全量映射和全量回刷

  目标：降低评论导入阶段的峰值内存和尾部耗时。

  实现方案：

  - 评论导入不再一次性把全量 business_ids、user_map 读进内存。
  - 改为分块策略：
      - 先根据目标业务集生成保留的 business_id 集合。
      - 用户导入后持久化 external_user_id -> user_id 的轻量映射来源。
      - 评论按批读取，按批查询命中的用户和商家主键，不保留全量 Python dict。
  - refresh_aggregated_review_counts() 改成增量：
      - 导入时收集受影响的 business 主键集合。
      - 仅回刷本次导入涉及的商家，不再全量刷新全部 YelpBusiness。
  - 导入输出补充结构化统计：
      - 扫描总行数
      - 命中业务筛选数
      - 因餐厅不在目标集被跳过数
      - 因用户不在目标集被跳过数
      - 实际写入/更新数

  ### 4. 给大表运行时路径补“展示集”和“构建集”边界

  目标：避免“库里有多少，登录页/推荐页就直面多少”。

  实现方案：

  - 区分三类数据边界：
      - 原始导入集：数据库里保留的 Yelp 主数据
      - 演示展示集：登录候选、首页示例、后台默认列表优先看的子集
      - 推荐构建集：允许参与 yelp_usercf.json 构建的评论/用户范围
  - 推荐默认：构建集不必覆盖库里所有 YelpReview。
  - 若后续仍需保留大规模导入能力：
      - 增加命令参数切换 --profile dev-demo|balanced|large
      - 不同 profile 固定样本规模和筛选规则
  - 运行时页面优先读取展示集或预计算结果，而不是临时从超大表中重聚合。

  ### 5. 明确本阶段优先级

  按你当前反馈，优先级应是：

  1. 解决登录首屏慢：去掉登录页实时聚合 Yelp 演示用户。
  2. 解决导入后续成本：把导入和回刷改成活跃度筛选 + 增量更新。
  3. 解决推荐构建成本：限制 build_yelp_review_usercf 的输入边界与默认规模。
  4. 最后再考虑是否保留“大规模留存模式”的工程化能力。

  ## Public Interfaces

  - import_yelp_data
      - 弱化或弃用单纯 --business-limit --user-limit --review-limit 的“前 N 行语义”
      - 新增推荐参数：
          - --profile dev-demo|balanced|large
          - --target-business-count
          - --target-user-count
          - --target-review-count
          - --min-business-review-count
          - --demo-candidate-count
  - 新增一个候选刷新命令，二选一：
      - refresh_yelp_demo_users
      - 或把该步骤合并进 import_yelp_data 的收尾流程
  - 若采用数据库预计算字段：
      - User.yelp_review_count
      - User.is_demo_candidate
      - 可选 User.last_yelp_review_at

  ## Test Plan

  必须覆盖以下场景：

  - 登录页 GET 不再触发全量 Yelp 评论聚合。
  - Yelp 演示账号候选来源在“无候选 / 少量候选 / 足量候选”下都能稳定返回。
  - 新导入策略下：
      - 只保留目标餐厅相关评论
      - 只保留命中评论涉及的用户
      - 不再因为 user-limit 前缀截断导致大量无效导入用户
  - 评论导入只增量刷新受影响商家的 aggregated_review_count。
  - 大规模数据下的命令输出包含新增的跳过原因和导入统计。
  - build_yelp_review_usercf 在构建集缩小时仍能生成可用 JSON，并对空结果稳定降级。
  - 登录首屏、Yelp 推荐页、餐厅详情页在“候选集存在/不存在”两种情况下都不报错。

  ## Assumptions

  - 当前最需要解释和解决的是运行时体验问题，尤其登录首屏慢，而不是继续追求全量 Yelp 落库。
  - 本项目的 Yelp 数据用途仍然是“演示推荐效果 + 本地开发”，不是生产级全量数据仓库。
  - 默认策略采用“按活跃度筛选的中等演示集”，不再把“原始文件前 N 行”作为主线。
  - 如果后续仍要保留百万级导入能力，应明确它是单独的 large profile，并接受与本地演示模式不同的运行成本。