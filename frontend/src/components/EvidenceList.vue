<template>
  <div v-if="!evidences.length" class="empty">未检索到证据 —— 这可能意味着内容缺少可查证来源，或证据不足。</div>
  <div v-else class="ev-list">
    <div v-for="e in evidences" :key="e.evidence_id" class="ev-item">
      <div class="ev-top">
        <el-tag size="small" :type="typeTag(e.source_type)">{{ typeLabel(e.source_type) }}</el-tag>
        <span class="src">{{ e.source_name || e.title || '未知来源' }}</span>
        <el-tag v-if="assess(e)?.is_authoritative" size="small" type="success" effect="plain">权威</el-tag>
        <el-tag v-if="assess(e)?.is_conflicting" size="small" type="danger" effect="plain">存在冲突</el-tag>
        <span class="score">可信度 {{ assess(e) ? assess(e).total_score.toFixed(2) : '—' }}</span>
      </div>
      <p class="text">{{ e.text }}</p>
      <div class="ev-bottom">
        <span class="method">检索方式：{{ e.retrieval_method || e.source_type }}</span>
        <a v-if="e.url" :href="e.url" target="_blank" rel="noopener" class="link">来源链接 ↗</a>
      </div>
      <div v-if="assess(e)?.conflict_note" class="conflict-note">⚠ {{ assess(e).conflict_note }}</div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  evidences: { type: Array, default: () => [] },
  assessmentMap: { type: Object, default: () => ({}) },
})

const TYPES = { web: ['网页', 'primary'], document: ['文档库', 'success'], vision: ['图片', 'warning'] }
function typeLabel(t) { return TYPES[t]?.[0] || t }
function typeTag(t) { return TYPES[t]?.[1] || 'info' }
function assess(e) {
  const id = e.evidence_id
  return props.assessmentMap?.[id] || null
}
</script>

<style scoped>
.empty { color: #909399; padding: 20px 0; }
.ev-list { display: flex; flex-direction: column; gap: 12px; }
.ev-item { border: 1px solid #ebeef5; border-radius: 8px; padding: 12px 16px; }
.ev-top { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.src { font-weight: 600; }
.score { margin-left: auto; color: #909399; font-size: 12px; }
.text { color: #606266; font-size: 14px; margin: 8px 0; line-height: 1.6; }
.ev-bottom { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: #909399; }
.link { color: #409eff; text-decoration: none; }
.conflict-note { background: #fef0f0; color: #f56c6c; padding: 6px 10px; border-radius: 6px; font-size: 12px; margin-top: 8px; }
</style>
