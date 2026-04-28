"use strict";
const { createApp, ref, reactive, onMounted, nextTick, watch } = Vue;

const API_BASE = '/api/v1';

const app = createApp({
  setup() {
    // State
    const activeTab = ref('dashboard');
    const tasks = ref([]);
    const agents = ref([]);
    const stats = reactive({
      total_tasks: 0, total_scans: 0, unique_targets: 0,
      open_ports: 0, filtered_ports: 0
    });

    // Task form
    const showTaskForm = ref(false);
    const taskLoading = ref(false);
    const taskForm = reactive({
      name: '', description: '', target_ips: '', port_range: '',
      protocol: 'tcp', scan_type: 'connect', timeout_ms: 3000,
      max_retries: 3, agent_ids: []
    });

    // Agent form
    const showAgentForm = ref(false);
    const agentForm = reactive({
      name: '', description: '', network_zone: '',
      max_concurrency: 50, rate_limit: 1000
    });

    // Asset search
    const ipSearchQuery = ref('');
    const ipExposureData = ref(null);

    // Graph
    const graphSearchQuery = ref('');
    const graphData = ref(null);
    let graphChartInstance = null;

    // Export
    const exportForm = reactive({
      format: 'csv', target_ip: '', start_time: '', end_time: ''
    });

    // API helpers
    async function api(path, options = {}) {
      const resp = await fetch(API_BASE + path, {
        headers: { 'Content-Type': 'application/json' },
        ...options
      });
      if (!resp.ok) throw new Error(`${resp.status}: ${resp.statusText}`);
      return resp.json();
    }

    // Load data
    async function loadTasks() {
      try {
        tasks.value = await api('/tasks/?limit=50');
        stats.total_tasks = tasks.value.length;
      } catch (e) { console.error('loadTasks:', e); }
    }

    async function loadAgents() {
      try {
        agents.value = await api('/agents/');
      } catch (e) { console.error('loadAgents:', e); }
    }

    async function loadStats() {
      try {
        const s = await api('/results/stats');
        Object.assign(stats, {
          total_scans: s.total || 0,
          unique_targets: s.unique_targets || 0,
          open_ports: s.open_count || 0,
          filtered_ports: s.filtered_count || 0,
        });
      } catch (e) { console.error('loadStats:', e); }
    }

    function renderResultChart() {
      const el = document.getElementById('resultChart');
      if (!el) return;
      const chart = echarts.init(el);
      chart.setOption({
        tooltip: { trigger: 'item' },
        legend: { bottom: 10 },
        series: [{
          type: 'pie',
          radius: ['40%', '70%'],
          avoidLabelOverlap: false,
          itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
          label: { show: false },
          emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
          data: [
            { value: stats.open_ports, name: 'Open', itemStyle: { color: '#16a34a' } },
            { value: stats.total_scans - stats.open_ports - stats.filtered_ports, name: 'Closed', itemStyle: { color: '#9ca3af' } },
            { value: stats.filtered_ports, name: 'Filtered', itemStyle: { color: '#f59e0b' } },
          ]
        }]
      });
      window.addEventListener('resize', () => chart.resize());
    }

    function renderGraphChart() {
      nextTick(() => {
        const el = document.getElementById('graphChart');
        if (!el || !graphData.value) return;
        if (graphChartInstance) graphChartInstance.dispose();
        graphChartInstance = echarts.init(el);

        const nodes = graphData.value.nodes.map(n => ({
          id: n.id,
          name: n.ip_address,
          symbolSize: n.ip_address === graphData.value.center_ip ? 60 : 40,
          itemStyle: {
            color: n.ip_address === graphData.value.center_ip ? '#2563eb' :
                   n.ip_type === 'public' ? '#16a34a' : '#f59e0b'
          },
          label: { show: true, position: 'bottom', formatter: '{b}' }
        }));

        const links = graphData.value.edges.map(e => ({
          source: e.from,
          target: e.to,
          label: { show: true, formatter: e.relation_type }
        }));

        graphChartInstance.setOption({
          tooltip: {},
          series: [{
            type: 'graph',
            layout: 'force',
            force: { repulsion: 400, edgeLength: 120 },
            roam: true,
            label: { show: true, fontSize: 12 },
            edgeSymbol: ['circle', 'arrow'],
            edgeSymbolSize: [4, 10],
            data: nodes,
            links: links,
            lineStyle: { color: '#9ca3af', curveness: 0.2 }
          }]
        });
        window.addEventListener('resize', () => graphChartInstance.resize());
      });
    }

    // Actions
    async function createTask() {
      taskLoading.value = true;
      try {
        const ips = taskForm.target_ips.split(',').map(s => s.trim());
        const body = {
          name: taskForm.name,
          description: taskForm.description,
          target_ips: ips,
          port_range: taskForm.port_range,
          protocol: taskForm.protocol,
          scan_type: taskForm.scan_type,
          timeout_ms: taskForm.timeout_ms,
          max_retries: taskForm.max_retries,
          agent_ids: taskForm.agent_ids.length ? taskForm.agent_ids : undefined
        };
        await api('/tasks/', { method: 'POST', body: JSON.stringify(body) });
        showTaskForm.value = false;
        Object.assign(taskForm, { name: '', description: '', target_ips: '', port_range: '', protocol: 'tcp', agent_ids: [] });
        await loadTasks();
        alert('Task created successfully!');
      } catch (e) { alert('Failed: ' + e.message); }
      finally { taskLoading.value = false; }
    }

    async function cancelTask(id) {
      if (!confirm('Cancel this task?')) return;
      await api(`/tasks/${id}/cancel`, { method: 'POST' });
      await loadTasks();
    }

    async function createAgent() {
      try {
        await api('/agents/', { method: 'POST', body: JSON.stringify({ ...agentForm }) });
        showAgentForm.value = false;
        Object.assign(agentForm, { name: '', description: '', network_zone: '', max_concurrency: 50, rate_limit: 1000 });
        await loadAgents();
      } catch (e) { alert('Failed: ' + e.message); }
    }

    async function toggleAgent(agent) {
      const action = agent.status === 'disabled' ? 'enable' : 'disable';
      await api(`/agents/${agent.id}/${action}`, { method: 'POST' });
      await loadAgents();
    }

    async function queryIpExposure() {
      if (!ipSearchQuery.value) return;
      try {
        ipExposureData.value = await api(`/results/ip/${ipSearchQuery.value}`);
      } catch (e) { alert('Failed: ' + e.message); }
    }

    async function queryGraph() {
      if (!graphSearchQuery.value) return;
      try {
        graphData.value = await api(`/graph/ip/${graphSearchQuery.value}`);
        renderGraphChart();
      } catch (e) { alert('Failed: ' + e.message); }
    }

    function getNodeIp(nodeId) {
      if (!graphData.value) return nodeId;
      const n = graphData.value.nodes.find(n => n.id === nodeId);
      return n ? n.ip_address : nodeId;
    }

    async function exportData() {
      const params = new URLSearchParams();
      if (exportForm.target_ip) params.set('target_ip', exportForm.target_ip);
      if (exportForm.start_time) params.set('start_time', exportForm.start_time);
      if (exportForm.end_time) params.set('end_time', exportForm.end_time);
      const url = `${API_BASE}/export/${exportForm.format}?${params}`;
      window.open(url, '_blank');
    }

    function formatTime(ts) {
      if (!ts) return '-';
      return new Date(ts).toLocaleString('zh-CN');
    }

    function viewTask(task) { alert(`Task: ${task.name}\nStatus: ${task.status}\nProgress: ${task.progress}%`); }

    // Lifecycle
    onMounted(async () => {
      await Promise.all([loadTasks(), loadAgents(), loadStats()]);
      setTimeout(renderResultChart, 100);
      // Auto-refresh
      setInterval(async () => {
        await loadTasks();
        await loadStats();
        renderResultChart();
      }, 10000);
    });

    watch(activeTab, (tab) => {
      if (tab === 'dashboard') setTimeout(renderResultChart, 100);
      if (tab === 'graph' && graphData.value) renderGraphChart();
    });

    return {
      activeTab, tasks, agents, stats,
      showTaskForm, taskLoading, taskForm,
      showAgentForm, agentForm,
      ipSearchQuery, ipExposureData,
      graphSearchQuery, graphData,
      exportForm,
      createTask, cancelTask, createAgent, toggleAgent,
      queryIpExposure, queryGraph, exportData,
      formatTime, viewTask, getNodeIp,
    };
  }
});

app.mount('#app');