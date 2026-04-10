/**
 * 图表组件模块
 *
 * Alpine.js 组件用于管理 ECharts 图表的加载、刷新和交互
 *
 * @module chart-components
 */

/**
 * 仪表板图表组件
 *
 * 管理四个图表的生命周期、数据加载和用户交互
 *
 * @returns {Object} Alpine.js 组件定义
 */
export function dashboardChart() {
  return {
    /** @type {number} 趋势图天数 */
    days: 30,

    /** @type {number} 地理图数据限制 */
    geoLimit: 1000,

    /** @type {number} 网络图节点限制 */
    networkLimit: 100,

    /** @type {Object|null} 图表1实例 */
    chart1: null,

    /** @type {Object|null} 图表2实例 */
    chart2: null,

    /** @type {Object|null} 图表3实例 */
    chart3: null,

    /** @type {Object|null} 图表4实例 */
    chart4: null,

    /**
     * 初始化组件
     * 创建图表实例并加载初始数据
     */
    init() {
      this.$nextTick(() => {
        this.initCharts();
        this.loadAllData();
      });
    },

    /**
     * 初始化四个图表实例
     * 配置ECharts选项（不含数据）
     */
    initCharts() {
      // 图表1: 分组柱状图+折线混合 - 菜品分类统计
      this.chart1 = echarts.init(document.getElementById('chart1'));
      this.chart1.setOption({
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'cross' }
        },
        legend: {
          data: ['平均价格', '平均收藏数'],
          bottom: 0
        },
        grid: {
          left: '3%',
          right: '3%',
          bottom: '15%',
          top: '10%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: [],
          axisLabel: { rotate: 30, fontSize: 10 }
        },
        yAxis: [
          {
            type: 'value',
            name: '价格(元)',
            position: 'left',
            axisLabel: { color: '#5470c6' }
          },
          {
            type: 'value',
            name: '收藏数',
            position: 'right',
            axisLabel: { color: '#91cc75' }
          }
        ],
        series: [
          {
            name: '平均价格',
            type: 'bar',
            data: [],
            itemStyle: { color: '#5470c6' },
            barWidth: '50%'
          },
          {
            name: '平均收藏数',
            type: 'line',
            yAxisIndex: 1,
            data: [],
            itemStyle: { color: '#91cc75' },
            smooth: true
          }
        ]
      });

      // 图表2: 多系列折线图 - 用户行为趋势
      this.chart2 = echarts.init(document.getElementById('chart2'));
      this.chart2.setOption({
        tooltip: {
          trigger: 'axis'
        },
        legend: {
          data: ['新用户注册', '新增收藏', '新增评论'],
          bottom: 0
        },
        grid: {
          left: '3%',
          right: '3%',
          bottom: '15%',
          top: '10%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: [],
          axisLabel: { rotate: 30, fontSize: 10 }
        },
        yAxis: {
          type: 'value',
          minInterval: 1
        },
        series: [
          {
            name: '新用户注册',
            type: 'line',
            data: [],
            smooth: true,
            itemStyle: { color: '#5470c6' },
            areaStyle: { opacity: 0.1 }
          },
          {
            name: '新增收藏',
            type: 'line',
            data: [],
            smooth: true,
            itemStyle: { color: '#91cc75' },
            areaStyle: { opacity: 0.1 }
          },
          {
            name: '新增评论',
            type: 'line',
            data: [],
            smooth: true,
            itemStyle: { color: '#fac858' },
            areaStyle: { opacity: 0.1 }
          }
        ]
      });

      // 图表3: 地理散点图 - 餐厅分布
      this.chart3 = echarts.init(document.getElementById('chart3'));

      // 图表4: 力导向图 - 相似度网络
      this.chart4 = echarts.init(document.getElementById('chart4'));

      // 响应式调整
      window.addEventListener('resize', () => {
        this.chart1?.resize();
        this.chart2?.resize();
        this.chart3?.resize();
        this.chart4?.resize();
      });
    },

    /**
     * 加载所有图表数据
     */
    loadAllData() {
      this.loadChart1();
      this.loadChart2();
      this.loadChart3();
      this.loadChart4();
    },

    /**
     * 加载图表1数据 - 菜品分类统计
     */
    loadChart1() {
      fetch('/api/v1/charts/food-category-stats/')
        .then(res => res.json())
        .then(result => {
          if (result.code === 200 && result.data) {
            this.chart1.setOption({
              xAxis: { data: result.data.categories },
              series: [
                { data: result.data.avgPrices },
                { data: result.data.avgCollects }
              ]
            });
          }
        })
        .catch(err => console.error('Chart1 load error:', err));
    },

    /**
     * 加载图表2数据 - 用户行为趋势
     */
    loadChart2() {
      fetch(`/api/v1/charts/user-activity-trend/?days=${this.days}`)
        .then(res => res.json())
        .then(result => {
          if (result.code === 200 && result.data) {
            this.chart2.setOption({
              xAxis: { data: result.data.dates },
              series: [
                { data: result.data.registrations },
                { data: result.data.collects },
                { data: result.data.comments }
              ]
            });
          }
        })
        .catch(err => console.error('Chart2 load error:', err));
    },

    /**
     * 加载图表3数据 - 美国餐厅地理分布
     */
    loadChart3() {
      fetch('/static/geo/usa.json')
        .then(res => res.json())
        .then(usaJson => {
          echarts.registerMap('usa', usaJson);
          return fetch(`/api/v1/charts/restaurant-geo/?limit=${this.geoLimit}`);
        })
        .then(res => res.json())
        .then(result => {
          if (result.code === 200 && result.data) {
            this.chart3.setOption({
              tooltip: {
                trigger: 'item',
                formatter: (params) => {
                  const v = params.value;
                  return `${params.name}<br/>
                          评分: ${v[2]}<br/>
                          评论数: ${v[3]}<br/>
                          城市: ${params.data.city || 'N/A'}, ${params.data.state || ''}`;
                }
              },
              visualMap: {
                min: 1,
                max: 5,
                left: 'left',
                top: 'bottom',
                text: ['高评分', '低评分'],
                calculable: true,
                inRange: {
                  color: ['#e0f3f8', '#abd9e9', '#74add1', '#4575b4', '#313695']
                }
              },
              geo: {
                map: 'usa',
                roam: true,
                itemStyle: {
                  areaColor: '#f3f3f3',
                  borderColor: '#999'
                },
                emphasis: {
                  itemStyle: {
                    areaColor: '#e6e6e6'
                  }
                }
              },
              series: [{
                name: '餐厅分布',
                type: 'scatter',
                coordinateSystem: 'geo',
                data: result.data,
                symbolSize: (val) => Math.max(5, Math.min(30, Math.log(val[3] + 1) * 3)),
                itemStyle: {
                  shadowBlur: 10,
                  shadowColor: 'rgba(0, 0, 0, 0.3)'
                }
              }]
            });
          }
        })
        .catch(err => console.error('Chart3 load error:', err));
    },

    /**
     * 加载图表4数据 - 相似度网络图
     */
    loadChart4() {
      fetch(`/api/v1/charts/similarity-network/?limit=${this.networkLimit}&threshold=0.5`)
        .then(res => res.json())
        .then(result => {
          if (result.code === 200 && result.data) {
            const data = result.data;

            this.chart4.setOption({
              tooltip: {
                trigger: 'item',
                formatter: (params) => {
                  if (params.dataType === 'edge') {
                    return `相似度: ${params.data.value}`;
                  }
                  return `${params.data.name}<br/>分类: ${params.data.category}`;
                }
              },
              legend: {
                data: data.categories ? data.categories.map(c => c.name) : [],
                top: 10,
                textStyle: { fontSize: 10 }
              },
              series: [{
                type: 'graph',
                layout: 'force',
                data: data.nodes,
                links: data.links,
                categories: data.categories,
                roam: true,
                label: {
                  show: false
                },
                force: {
                  repulsion: 100,
                  gravity: 0.1,
                  edgeLength: [50, 200]
                },
                lineStyle: {
                  color: 'source',
                  curveness: 0.3,
                  width: (params) => params.data.value * 3
                },
                emphasis: {
                  focus: 'adjacency',
                  lineStyle: {
                    width: 5
                  }
                }
              }]
            });
          }
        })
        .catch(err => console.error('Chart4 load error:', err));
    }
  };
}
