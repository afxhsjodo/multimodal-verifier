<template>
  <el-card shadow="never" class="card">
    <template #header><span class="card-title">Agent 执行过程</span></template>
    <div class="flow">
      <el-timeline v-for="s in steps" :key="s.ts + s.action + s.summary">
        <el-timeline-item
          :timestamp="s.ts || ''"
          :type="typeOf(s.agent)"
          :hollow="false"
        >
          <div class="step">
            <span class="agent">{{ labelOf(s.agent) }}</span>
            <span class="action">{{ s.action }}</span>
            <span class="dur">{{ (s.duration_ms / 1000).toFixed(1) }}s</span>
          </div>
          <div class="summary" v-if="s.summary">{{ s.summary }}</div>
        </el-timeline-item>
      </el-timeline>
    </div>
  </el-card>
</template>

<script setup>
defineProps({ steps: { type: Array, default: () => [] } })

const LABELS = {
  claim_decompose: '主张拆解',
  retrieval_plan: '检索规划',
  evidence_retrieval: '证据获取',
  credibility_assess: '可信度评估',
  conclusion: '结论生成',
}
function labelOf(agent) {
  return LABELS[agent] || agent
}
const TYPES = { claim_decompose: 'primary', retrieval_plan: 'primary', evidence_retrieval: 'warning', credibility_assess: 'warning', conclusion: 'success' }
function typeOf(agent) {
  return TYPES[agent] || 'primary'
}
</script>

<style scoped>
.card { margin-top: 4px; }
.card-title { font-weight: 600; }
.step { display: flex; align-items: center; gap: 10px; }
.agent { font-weight: 600; color: #409eff; }
.action { color: #606266; }
.dur { color: #c0c4cc; font-size: 12px; }
.summary { color: #909399; font-size: 13px; margin-top: 4px; }
</style>
